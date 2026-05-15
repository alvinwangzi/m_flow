import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PlaygroundMarkdownMessage } from "../PlaygroundMarkdownMessage";

describe("PlaygroundMarkdownMessage", () => {
  it("renders markdown elements", () => {
    render(
      <PlaygroundMarkdownMessage
        content={"# Title\n\n- item 1\n- item 2\n\n`code`\n\n[link](https://example.com)"}
      />
    );

    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getByText("item 1")).toBeInTheDocument();
    expect(screen.getByText("code")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "link" })).toHaveAttribute("href", "https://example.com");
  });

  it("renders inline html line breaks and strong text", () => {
    const { container } = render(
      <PlaygroundMarkdownMessage
        content={"- 德锐咨询更偏向于**“精专深”**<br>尤其在人力资源战略<br>与变革"}
      />
    );

    expect(container.querySelector("strong")).not.toBeNull();
    expect(container.querySelectorAll("br").length).toBeGreaterThanOrEqual(2);
    expect(container.textContent).toContain("尤其在人力资源战略");
    expect(container.textContent).toContain("与变革");
  });
});
