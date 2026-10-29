import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, test, expect } from "vitest";
import App from "../App";
import { getToken, setToken } from "../api";

const session = {
  name: "Priya Shah",
  ai_mode: "mock",
  organizations: [
    { org_id: 1, org_name: "Northwind Logistics", role: "employee" },
  ],
};

test.each(["network", "server"])(
  "a temporary %s failure preserves sign-in and allows a successful retry",
  async (failure) => {
    setToken("existing-test-token");
    const fetch = vi.spyOn(globalThis, "fetch");
    if (failure === "network")
      fetch.mockRejectedValueOnce(new TypeError("Offline"));
    else
      fetch.mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Temporarily unavailable" }), {
          status: 503,
        }),
      );
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify(session), { status: 200 }),
    );
    render(<App />);
    expect(
      await screen.findByText(/Cannot reach AI Pulse|Temporarily unavailable/),
    ).toBeInTheDocument();
    expect(getToken()).toBe("existing-test-token");
    expect(
      screen.queryByRole("heading", { name: /A clearer starting point/ }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", {
        name: "Where are we working today?",
      }),
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  },
);

test("a rejected session is cleared and requires sign-in", async () => {
  setToken("expired-test-token");
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    new Response(JSON.stringify({ detail: "Your session has expired." }), {
      status: 401,
    }),
  );
  render(<App />);
  expect(
    await screen.findByRole("button", { name: "Sign in", exact: true }),
  ).toBeInTheDocument();
  expect(getToken()).toBeNull();
  expect(
    screen.queryByRole("button", { name: "Try again" }),
  ).not.toBeInTheDocument();
});
