import operator
from datetime import datetime
from typing import Any, List, Optional

import strawberry
from aioitertools.itertools import islice
from sqlalchemy import and_, desc, distinct, select
from sqlalchemy.orm import contains_eager
from sqlalchemy.sql.expression import tuple_
from strawberry import ID, UNSET
from strawberry.types import Info

from phoenix.datetime_utils import right_open_time_range
from phoenix.db import models
from phoenix.server.api.context import Context
from phoenix.server.api.input_types.SpanSort import SpanSort, SpanSortConfig
from phoenix.server.api.input_types.TimeRange import TimeRange
from phoenix.server.api.types.DocumentEvaluationSummary import DocumentEvaluationSummary
from phoenix.server.api.types.EvaluationSummary import EvaluationSummary
from phoenix.server.api.types.node import Node
from phoenix.server.api.types.pagination import (
    Connection,
    Cursor,
    CursorSortColumn,
    CursorString,
    connections,
)
from phoenix.server.api.types.SortDir import SortDir
from phoenix.server.api.types.Span import Span, to_gql_span
from phoenix.server.api.types.Trace import Trace
from phoenix.server.api.types.ValidationResult import ValidationResult
from phoenix.trace.dsl import SpanFilter

SPANS_LIMIT = 1000


@strawberry.type
class Project(Node):
    name: str
    gradient_start_color: str
    gradient_end_color: str

    @strawberry.field
    async def start_time(
        self,
        info: Info[Context, None],
    ) -> Optional[datetime]:
        start_time = await info.context.data_loaders.min_start_or_max_end_times.load(
            (self.id_attr, "start"),
        )
        start_time, _ = right_open_time_range(start_time, None)
        return start_time

    @strawberry.field
    async def end_time(
        self,
        info: Info[Context, None],
    ) -> Optional[datetime]:
        end_time = await info.context.data_loaders.min_start_or_max_end_times.load(
            (self.id_attr, "end"),
        )
        _, end_time = right_open_time_range(None, end_time)
        return end_time

    @strawberry.field
    async def record_count(
        self,
        info: Info[Context, None],
        time_range: Optional[TimeRange] = UNSET,
        filter_condition: Optional[str] = UNSET,
    ) -> int:
        return await info.context.data_loaders.record_counts.load(
            ("span", self.id_attr, time_range, filter_condition),
        )

    @strawberry.field
    async def trace_count(
        self,
        info: Info[Context, None],
        time_range: Optional[TimeRange] = UNSET,
    ) -> int:
        return await info.context.data_loaders.record_counts.load(
            ("trace", self.id_attr, time_range, None),
        )

    @strawberry.field
    async def token_count_total(
        self,
        info: Info[Context, None],
        time_range: Optional[TimeRange] = UNSET,
        filter_condition: Optional[str] = UNSET,
    ) -> int:
        return await info.context.data_loaders.token_counts.load(
            ("total", self.id_attr, time_range, filter_condition),
        )

    @strawberry.field
    async def token_count_prompt(
        self,
        info: Info[Context, None],
        time_range: Optional[TimeRange] = UNSET,
        filter_condition: Optional[str] = UNSET,
    ) -> int:
        return await info.context.data_loaders.token_counts.load(
            ("prompt", self.id_attr, time_range, filter_condition),
        )

    @strawberry.field
    async def token_count_completion(
        self,
        info: Info[Context, None],
        time_range: Optional[TimeRange] = UNSET,
        filter_condition: Optional[str] = UNSET,
    ) -> int:
        return await info.context.data_loaders.token_counts.load(
            ("completion", self.id_attr, time_range, filter_condition),
        )

    @strawberry.field
    async def latency_ms_quantile(
        self,
        info: Info[Context, None],
        probability: float,
        time_range: Optional[TimeRange] = UNSET,
    ) -> Optional[float]:
        return await info.context.data_loaders.latency_ms_quantile.load(
            ("trace", self.id_attr, time_range, None, probability),
        )

    @strawberry.field
    async def span_latency_ms_quantile(
        self,
        info: Info[Context, None],
        probability: float,
        time_range: Optional[TimeRange] = UNSET,
        filter_condition: Optional[str] = UNSET,
    ) -> Optional[float]:
        return await info.context.data_loaders.latency_ms_quantile.load(
            ("span", self.id_attr, time_range, filter_condition, probability),
        )

    @strawberry.field
    async def trace(self, trace_id: ID, info: Info[Context, None]) -> Optional[Trace]:
        stmt = (
            select(models.Trace.id)
            .where(models.Trace.trace_id == str(trace_id))
            .where(models.Trace.project_rowid == self.id_attr)
        )
        async with info.context.db() as session:
            if (id_attr := await session.scalar(stmt)) is None:
                return None
        return Trace(id_attr=id_attr)

    @strawberry.field
    async def spans(
        self,
        info: Info[Context, None],
        time_range: Optional[TimeRange] = UNSET,
        first: Optional[int] = 50,
        last: Optional[int] = UNSET,
        after: Optional[CursorString] = UNSET,
        before: Optional[CursorString] = UNSET,
        sort: Optional[SpanSort] = UNSET,
        root_spans_only: Optional[bool] = UNSET,
        filter_condition: Optional[str] = UNSET,
    ) -> Connection[Span]:
        stmt = (
            select(models.Span)
            .join(models.Trace)
            .where(models.Trace.project_rowid == self.id_attr)
            .options(contains_eager(models.Span.trace))
        )
        if time_range:
            stmt = stmt.where(
                and_(
                    time_range.start <= models.Span.start_time,
                    models.Span.start_time < time_range.end,
                )
            )
        if root_spans_only:
            # A root span is any span whose parent span is missing in the
            # database, even if its `parent_span_id` may not be NULL.
            parent = select(models.Span.span_id).alias()
            stmt = stmt.outerjoin(
                parent,
                models.Span.parent_id == parent.c.span_id,
            ).where(parent.c.span_id.is_(None))
        if filter_condition:
            span_filter = SpanFilter(condition=filter_condition)
            stmt = span_filter(stmt)
        sort_config: Optional[SpanSortConfig] = None
        cursor_rowid_column: Any = models.Span.id
        if sort:
            sort_config = sort.update_orm_expr(stmt)
            stmt = sort_config.stmt
            if sort_config.dir is SortDir.desc:
                cursor_rowid_column = desc(cursor_rowid_column)
        if after:
            cursor = Cursor.from_string(after)
            if sort_config and cursor.sort_column:
                sort_column = cursor.sort_column
                compare = operator.lt if sort_config.dir is SortDir.desc else operator.gt
                stmt = stmt.where(
                    compare(
                        tuple_(sort_config.orm_expression, models.Span.id),
                        (sort_column.value, cursor.rowid),
                    )
                )
            else:
                stmt = stmt.where(models.Span.id > cursor.rowid)
        if first:
            stmt = stmt.limit(
                first + 1  # overfetch by one to determine whether there's a next page
            )
        stmt = stmt.order_by(cursor_rowid_column)
        data = []
        async with info.context.db() as session:
            span_records = await session.execute(stmt)
            async for span_record in islice(span_records, first):
                span = span_record[0]
                eval_value = span_record[1] if len(span_record) > 1 else None
                cursor = Cursor(
                    rowid=span.id,
                    sort_column=(
                        CursorSortColumn(
                            type=sort_config.column_data_type,
                            value=eval_value
                            if eval_value is not None
                            else getattr(span, sort_config.column_name),
                        )
                        if sort_config
                        else None
                    ),
                )
                data.append((cursor, to_gql_span(span)))
            has_next_page = True
            try:
                next(span_records)
            except StopIteration:
                has_next_page = False

        return connections(
            data,
            has_previous_page=False,
            has_next_page=has_next_page,
        )

    @strawberry.field(
        description="Names of all available evaluations for traces. "
        "(The list contains no duplicates.)"
    )  # type: ignore
    async def trace_evaluation_names(
        self,
        info: Info[Context, None],
    ) -> List[str]:
        stmt = (
            select(distinct(models.TraceAnnotation.name))
            .join(models.Trace)
            .where(models.Trace.project_rowid == self.id_attr)
            .where(models.TraceAnnotation.annotator_kind == "LLM")
        )
        async with info.context.db() as session:
            return list(await session.scalars(stmt))

    @strawberry.field(
        description="Names of all available evaluations for spans. "
        "(The list contains no duplicates.)"
    )  # type: ignore
    async def span_evaluation_names(
        self,
        info: Info[Context, None],
    ) -> List[str]:
        stmt = (
            select(distinct(models.SpanAnnotation.name))
            .join(models.Span)
            .join(models.Trace, models.Span.trace_rowid == models.Trace.id)
            .where(models.Trace.project_rowid == self.id_attr)
            .where(models.SpanAnnotation.annotator_kind == "LLM")
        )
        async with info.context.db() as session:
            return list(await session.scalars(stmt))

    @strawberry.field(
        description="Names of available document evaluations.",
    )  # type: ignore
    async def document_evaluation_names(
        self,
        info: Info[Context, None],
        span_id: Optional[ID] = UNSET,
    ) -> List[str]:
        stmt = (
            select(distinct(models.DocumentAnnotation.name))
            .join(models.Span)
            .join(models.Trace, models.Span.trace_rowid == models.Trace.id)
            .where(models.Trace.project_rowid == self.id_attr)
            .where(models.DocumentAnnotation.annotator_kind == "LLM")
        )
        if span_id:
            stmt = stmt.where(models.Span.span_id == str(span_id))
        async with info.context.db() as session:
            return list(await session.scalars(stmt))

    @strawberry.field
    async def trace_evaluation_summary(
        self,
        info: Info[Context, None],
        evaluation_name: str,
        time_range: Optional[TimeRange] = UNSET,
    ) -> Optional[EvaluationSummary]:
        return await info.context.data_loaders.evaluation_summaries.load(
            ("trace", self.id_attr, time_range, None, evaluation_name),
        )

    @strawberry.field
    async def span_evaluation_summary(
        self,
        info: Info[Context, None],
        evaluation_name: str,
        time_range: Optional[TimeRange] = UNSET,
        filter_condition: Optional[str] = UNSET,
    ) -> Optional[EvaluationSummary]:
        return await info.context.data_loaders.evaluation_summaries.load(
            ("span", self.id_attr, time_range, filter_condition, evaluation_name),
        )

    @strawberry.field
    async def document_evaluation_summary(
        self,
        info: Info[Context, None],
        evaluation_name: str,
        time_range: Optional[TimeRange] = UNSET,
        filter_condition: Optional[str] = UNSET,
    ) -> Optional[DocumentEvaluationSummary]:
        return await info.context.data_loaders.document_evaluation_summaries.load(
            (self.id_attr, time_range, filter_condition, evaluation_name),
        )

    @strawberry.field
    def streaming_last_updated_at(
        self,
        info: Info[Context, None],
    ) -> Optional[datetime]:
        return info.context.streaming_last_updated_at(self.id_attr)

    @strawberry.field
    async def validate_span_filter_condition(self, condition: str) -> ValidationResult:
        # TODO(persistence): this query is too expensive to run on every validation
        # valid_eval_names = await self.span_evaluation_names()
        try:
            SpanFilter(
                condition=condition,
                # valid_eval_names=valid_eval_names,
            )
            return ValidationResult(is_valid=True, error_message=None)
        except SyntaxError as e:
            return ValidationResult(
                is_valid=False,
                error_message=e.msg,
            )
