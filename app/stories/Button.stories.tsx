import React from "react";
import { Meta, StoryFn } from "@storybook/react";
import { css } from "@emotion/react";

import { Button, ButtonProps } from "@phoenix/components";

import { ThemeWrapper } from "./components/ThemeWrapper";

const meta: Meta = {
  title: "Button",
  component: Button,
  parameters: {
    controls: { expanded: true },
  },
};

export default meta;

const Template: StoryFn<ButtonProps> = (args) => (
  <ThemeWrapper>
    <Button {...args} />
  </ThemeWrapper>
);

export const Default = Template.bind({});

Default.args = {
  children: "Button",
};

export const CustomCSS = Template.bind({});

CustomCSS.args = {
  css: css`
    /* TODO: we need to make it simpler to not have to make styles more specific */
    border-color: var(--ac-global-color-primary) !important;
  `,
  children: "Custom",
};
