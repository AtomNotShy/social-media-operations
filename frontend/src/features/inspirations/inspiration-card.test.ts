import { createElement } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { InspirationCard } from "./inspiration-card";
import { demoInspirations } from "@/src/test/fixtures";

describe("InspirationCard", () => {
  afterEach(cleanup);

  it("shows the latest qualified score and available interaction evidence", () => {
    render(
      createElement(InspirationCard, {
        item: demoInspirations[0],
        href: "/w/demo/inspirations/demo",
      }),
    );

    expect(screen.getByText("T1")).toBeTruthy();
    expect(screen.getByText("R 5.74×")).toBeTruthy();
    expect(screen.getByText("互动 8,394")).toBeTruthy();
  });

  it("does not invent score or metric labels when the list has no evidence", () => {
    render(
      createElement(InspirationCard, {
        item: demoInspirations[1],
        href: "/w/demo/inspirations/demo-2",
      }),
    );

    expect(screen.queryByText("T1")).toBeNull();
    expect(screen.queryByText(/R .*×/)).toBeNull();
    expect(screen.queryByText(/^互动 /)).toBeNull();
  });
});
