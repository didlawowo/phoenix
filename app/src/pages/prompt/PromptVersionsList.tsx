import React from "react";
import { useFragment } from "react-relay";
import { graphql } from "react-relay";
import { useNavigate } from "react-router";
import { css } from "@emotion/react";

import { Button, Flex, Text, View } from "@arizeai/components";

import { Truncate } from "@phoenix/components/utility/Truncate";

import {
  PromptVersionsList__main$data,
  PromptVersionsList__main$key,
} from "./__generated__/PromptVersionsList__main.graphql";

export type PromptVersionItemProps = {
  version: PromptVersionsList__main$data["promptVersions"]["edges"][number]["version"];
};

const promptVersionItemCSS = css`
  & {
    border-bottom: 1px solid var(--ac-global-color-grey-300);
  }

  & > * {
    width: 100%;
    justify-content: flex-start;
    padding: 0;
  }
`;

/**
 * A single prompt version item, displaying the version number,
 * the date it was created, and tag. Clicking the item will
 * add /:versionId to the current path
 */
export const PromptVersionItem = ({ version }: PromptVersionItemProps) => {
  const navigate = useNavigate();
  return (
    <div css={promptVersionItemCSS}>
      <Button onClick={() => navigate(`${version.id}`)} variant="quiet">
        <Flex width="100%" height={96} direction="row">
          <View padding="size-200">
            <Flex direction="column">
              <Text>{version.id}</Text>
              <Truncate maxWidth={"100%"}>
                <Text>{version.description}</Text>
              </Truncate>
            </Flex>
          </View>
        </Flex>
      </Button>
    </div>
  );
};

type PromptVersionsListProps = {
  prompt: PromptVersionsList__main$key;
};

/**
 * Full height, scrollable, list of prompt versions
 */
export const PromptVersionsList = ({ prompt }: PromptVersionsListProps) => {
  const { promptVersions } = useFragment(
    graphql`
      fragment PromptVersionsList__main on Prompt {
        promptVersions {
          edges {
            version: node {
              id
              ... on PromptVersion {
                id
                description
              }
            }
          }
        }
      }
    `,
    prompt
  );
  return (
    <View height="100%" overflow="scroll">
      <Flex direction="column" width={300}>
        {promptVersions.edges.map(({ version }) => (
          <PromptVersionItem key={version.id} version={version} />
        ))}
      </Flex>
    </View>
  );
};
