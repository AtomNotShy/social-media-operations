import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { ContentPackagePanel } from "@/src/features/production/content-package-panel";
import { demoProjects, demoScripts } from "@/src/features/production/fixtures";

afterEach(cleanup);

function renderPanel(canEdit: boolean) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const project = demoProjects[0];
  const scripts = demoScripts.filter(
    (item) => item.content_project_id === project.id,
  );
  return render(
    createElement(
      QueryClientProvider,
      { client },
      createElement(ContentPackagePanel, {
        workspaceId: "demo",
        projectId: project.id,
        project: { id: project.id, version: project.version, title: project.title },
        scripts,
        canEdit,
      }),
    ),
  );
}

describe("content package panel", () => {
  it("lists the generated package and shows scenes and titles", async () => {
    renderPanel(false);

    expect(await screen.findByText("小红书 · v1")).toBeTruthy();
    expect(screen.getByText(/3 个分镜 · 45 秒/)).toBeTruthy();
    expect(
      screen.getByText("一周发 14 条，线索还是 0：问题不在勤奋。"),
    ).toBeTruthy();
    expect(
      screen.getByText("发 14 条线索为 0？问题不在勤奋"),
    ).toBeTruthy();
  });

  it("hides edit controls for viewers", async () => {
    renderPanel(false);
    await screen.findByText("小红书 · v1");
    expect(
      screen.queryByRole("button", { name: "编辑为新版本" }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: "冻结" })).toBeNull();
  });

  it("edits scenes into a new version and selects it", async () => {
    renderPanel(true);
    await screen.findByText("小红书 · v1");

    fireEvent.click(
      screen.getByRole("button", { name: "编辑为新版本" }),
    );
    expect(screen.getByText(/保存会追加一个新版本/)).toBeTruthy();

    const screenTextInput = screen.getAllByLabelText("屏显文字")[0];
    fireEvent.change(screenTextInput, { target: { value: "新版屏显" } });
    fireEvent.click(
      screen.getByRole("button", { name: "保存为新版本" }),
    );

    expect(await screen.findByText("小红书 · v2")).toBeTruthy();
    expect(screen.getByText(/新版屏显/)).toBeTruthy();
  });
});
