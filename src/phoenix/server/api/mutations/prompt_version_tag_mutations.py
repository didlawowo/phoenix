import strawberry
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError as PostgreSQLIntegrityError
from sqlean.dbapi2 import IntegrityError as SQLiteIntegrityError  # type: ignore[import-untyped]
from strawberry.types import Info

from phoenix.db import models
from phoenix.db.helpers import SupportedSQLDialect
from phoenix.db.insertion.helpers import insert_on_conflict
from phoenix.server.api.context import Context
from phoenix.server.api.exceptions import BadRequest, Conflict
from phoenix.server.api.input_types.PromptVersionTagInput import SetPromptVersionTagInput
from phoenix.server.api.queries import Query
from phoenix.server.api.types.node import from_global_id_with_expected_type
from phoenix.server.api.types.PromptVersion import PromptVersion
from phoenix.server.api.types.PromptVersionTag import PromptVersionTag, to_gql_prompt_version_tag


@strawberry.type
class PromptVersionTagMutationPayload:
    prompt_version_tag: PromptVersionTag
    query: Query


@strawberry.type
class PromptVersionTagMutationMixin:
    @strawberry.mutation
    async def set_prompt_version_tag(
        self, info: Info[Context, None], input: SetPromptVersionTagInput
    ) -> PromptVersionTagMutationPayload:
        async with info.context.db() as session:
            prompt_version_id = from_global_id_with_expected_type(
                input.prompt_version_id, PromptVersion.__name__
            )
            prompt_version = await session.scalar(
                select(models.PromptVersion).where(models.PromptVersion.id == prompt_version_id)
            )
            if not prompt_version:
                raise BadRequest("PromptVersion with ID {input.prompt_version_id} not found.")

            prompt_id = prompt_version.prompt_id

            tag_values = {
                "name": input.name,
                "description": input.description,
                "prompt_id": prompt_id,
                "prompt_version_id": prompt_version_id,
            }

            dialect = SupportedSQLDialect(session.bind.dialect.name)
            updated_tag = await session.scalar(
                insert_on_conflict(
                    tag_values,
                    dialect=dialect,
                    table=models.PromptVersionTag,
                    unique_by=("name", "prompt_id"),
                ).returning(models.PromptVersionTag)
            )

            if not updated_tag:
                raise BadRequest("Failed to create or update PromptVersionTag.")

            try:
                await session.commit()
            except (PostgreSQLIntegrityError, SQLiteIntegrityError):
                raise Conflict("Failed to update PromptVersionTag.")

            version_tag = to_gql_prompt_version_tag(updated_tag)
            return PromptVersionTagMutationPayload(prompt_version_tag=version_tag, query=Query())
