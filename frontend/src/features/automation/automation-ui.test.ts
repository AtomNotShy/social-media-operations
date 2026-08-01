import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { AutomationSettingsPanel } from "@/src/features/automation/automation-settings-panel";
import { AutomationTodayPanel } from "@/src/features/automation/automation-today-panel";

afterEach(cleanup);

function renderWithClient(element: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    createElement(QueryClientProvider, { client }, element),
  );
}

describe("automation settings", () => {
  it("explains the zero-AI gate and only lets owners edit it", async () => {
    renderWithClient(
      createElement(AutomationSettingsPanel, {
        canManage: true,
        workspaceId: "demo",
      }),
    );

    expect(await screen.findByText("自动发现与分析")).toBeTruthy();
    expect(screen.getByText(/未达标只进入观察池/)).toBeTruthy();
    expect(screen.getByText(/阈值为 0 表示不启用/)).toBeTruthy();
    expect(screen.getByRole("option", { name: "任一指标达标" })).toBeTruthy();

    const scanInterval = screen.getByRole("spinbutton", {
      name: /扫描间隔（小时）/,
    });
    fireEvent.change(scanInterval, {
      target: { value: "12" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存自动化设置" }));
    expect(await screen.findByText("已保存")).toBeTruthy();
    expect((scanInterval as HTMLInputElement).value).toBe("12");
  });

  it("renders viewer settings as read-only", async () => {
    renderWithClient(
      createElement(AutomationSettingsPanel, {
        canManage: false,
        workspaceId: "demo",
      }),
    );

    expect(await screen.findByText(/只有 Owner 可以修改/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "保存自动化设置" })).toBeNull();
  });
});

describe("today automation summary", () => {
  it("shows the funnel and links qualified candidates to evidence", async () => {
    renderWithClient(
      createElement(AutomationTodayPanel, { workspaceId: "demo" }),
    );

    expect(await screen.findByText("今日自动发现")).toBeTruthy();
    expect(screen.getByText("扫描账号")).toBeTruthy();
    expect(screen.getByText("通过门槛")).toBeTruthy();
    expect(screen.getByText("L2 完成")).toBeTruthy();
    expect(screen.getByText("今日精选候选")).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: /一个被忽略的增长信号/ })
        .getAttribute("href"),
    ).toBe("/w/demo/inspirations/demo-inspiration-001");
  });
});
