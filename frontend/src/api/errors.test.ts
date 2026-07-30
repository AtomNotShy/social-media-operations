import { describe, expect, it } from "vitest";
import { toAppError } from "./errors";

describe("problem details mapping", () => {
  it("keeps stable error and request identifiers", async () => {
    const error = await toAppError(
      new Response(
        JSON.stringify({
          code: "FORBIDDEN",
          detail: "You cannot edit this workspace.",
          request_id: "request-123",
          retryable: false,
        }),
        { status: 403, headers: { "content-type": "application/problem+json" } },
      ),
    );

    expect(error).toEqual({
      code: "FORBIDDEN",
      message: "You cannot edit this workspace.",
      status: 403,
      requestId: "request-123",
      retryable: false,
    });
  });

  it("normalizes non-JSON server failures", async () => {
    const error = await toAppError(
      new Response("Bad gateway", { status: 502 }),
    );
    expect(error.code).toBe("REQUEST_FAILED");
    expect(error.retryable).toBe(true);
  });
});
