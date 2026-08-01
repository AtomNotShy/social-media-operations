import { describe, expect, it } from "vitest";
import {
  formatCompactNumber,
  isTerminalJob,
  jobErrorLabel,
  jobStatusLabel,
  jobTypeLabel,
  platformLabel,
} from "./format";

describe("format helpers", () => {
  it("keeps missing metrics distinct from zero", () => {
    expect(formatCompactNumber(null)).toBe("—");
    expect(formatCompactNumber(0)).toBe("0");
  });

  it("maps platform and job language for users", () => {
    expect(platformLabel("xiaohongshu")).toBe("小红书");
    expect(jobStatusLabel("retry_wait")).toBe("等待重试");
  });

  it("maps every supported background job type to a Chinese label", () => {
    expect(jobTypeLabel("PROFILE_SCAN")).toBe("对标账号同步");
    expect(jobTypeLabel("CONTENT_DETAIL_FETCH")).toBe("内容详情采集");
    expect(jobTypeLabel("AI_ANALYSIS")).toBe("AI 内容分析");
    expect(jobTypeLabel("TRANSCRIBE")).toBe("内容转写");
    expect(jobTypeLabel("CONTENT_GENERATION")).toBe("内容生成");
    expect(jobTypeLabel("COMMENT_FETCH")).toBe("评论采集");
    expect(jobTypeLabel("DISCOVERY_SEARCH")).toBe("内容搜索");
    expect(jobTypeLabel("VIDEO_PRODUCTION")).toBe("视频制作");
    expect(jobTypeLabel("UNREGISTERED_JOB")).toBe("其他后台任务");
  });

  it("maps job errors to Chinese copy with a Chinese fallback", () => {
    expect(jobErrorLabel("PROVIDER_ERROR")).toBe("数据源请求失败，请稍后重试。");
    expect(jobErrorLabel("AI_OUTPUT_TRUNCATED")).toBe(
      "AI 输出超出长度限制，未能生成完整结果。",
    );
    expect(jobErrorLabel("UNREGISTERED_ERROR")).toBe(
      "任务执行失败，请查看后端日志或稍后重试。",
    );
  });

  it("stops polling only for terminal jobs", () => {
    expect(isTerminalJob("running")).toBe(false);
    expect(isTerminalJob("failed")).toBe(true);
    expect(isTerminalJob("cancelled")).toBe(true);
  });
});
