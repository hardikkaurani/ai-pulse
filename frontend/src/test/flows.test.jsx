import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, test, expect } from "vitest";
import Dashboard from "../pages/Dashboard";
import Diagnostic from "../pages/Diagnostic";
import Plan from "../pages/Plan";
import Report from "../pages/Report";
import { DeleteDialog } from "../components";
import { api } from "../api";
vi.mock("../api", () => ({ api: vi.fn() }));

test("protected department never displays a numeric score or count", async () => {
  api.mockResolvedValue({
    ai_mode: "mock",
    updated_at: "2026-10-28T10:00:00Z",
    departments: [
      {
        department: "HR",
        protected: true,
        responded: null,
        average_score: null,
        risks: [],
      },
    ],
  });
  render(<Dashboard />);
  expect(
    await screen.findByText("HR", { selector: "strong" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Results protected")).toBeInTheDocument();
  expect(screen.getByText("Privacy comes first")).toBeInTheDocument();
  expect(screen.queryByText("0 / 5")).not.toBeInTheDocument();
});

test("a suppressed risk count is protected without claiming a numeric range", async () => {
  api.mockResolvedValue({
    ai_mode: "mock",
    updated_at: "2026-10-28T10:00:00Z",
    departments: [
      {
        department: "Support",
        protected: false,
        responded: 6,
        average_score: 3,
        level: "Developing",
        risks: [
          {
            key: "unreviewed_output",
            label: "AI output used without review",
            people: null,
          },
        ],
      },
    ],
  });
  render(<Dashboard />);
  expect(
    await screen.findByText("AI output used without review"),
  ).toBeInTheDocument();
  expect(screen.getByText("Protected")).toBeInTheDocument();
  expect(screen.queryByText("0–4 people")).not.toBeInTheDocument();
});

test("assessment requires an answer before advancing and saves the complete payload", async () => {
  const user = userEvent.setup(),
    onDone = vi.fn();
  api.mockImplementation((path) =>
    Promise.resolve(
      path === "/diagnostic/questions"
        ? [
            {
              id: "one",
              type: "mcq",
              text: "How often?",
              options: ["Never", "Daily"],
            },
            {
              id: "two",
              type: "open",
              text: "Describe your work.",
              options: [],
            },
          ]
        : { status: "completed" },
    ),
  );
  render(<Diagnostic mode="mock" onDone={onDone} onCancel={() => {}} />);
  expect(await screen.findByText("How often?")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  await user.click(screen.getByLabelText(/Daily/));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.type(
    screen.getByLabelText("Your written answer"),
    "Reviewed a fictional draft carefully.",
  );
  await user.click(screen.getByRole("button", { name: "Review answers" }));
  await user.click(screen.getByRole("button", { name: "Submit assessment" }));
  await waitFor(() => expect(onDone).toHaveBeenCalled());
  const call = api.mock.calls.find((c) => c[0] === "/diagnostic/submit");
  expect(JSON.parse(call[1].body).answers).toHaveLength(2);
});

test("a failed AI result is visibly pending and never rendered as a score", async () => {
  api.mockResolvedValue({
    status: "pending",
    name: "Priya",
    average_score: null,
    actions: [],
  });
  render(<Report onNavigate={() => {}} />);
  expect(
    await screen.findByText("Waiting for a valid AI result"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Retry scoring" }),
  ).toBeInTheDocument();
  expect(screen.queryByText(/OUT OF 5/)).not.toBeInTheDocument();
});

test("activity completion is saved and undoable", async () => {
  const user = userEvent.setup();
  const activity = {
    id: "private-id",
    title: "Check three claims",
    why: "Review is useful.",
    role_example: "a reply",
    steps: ["Check"],
    success: "Three checked.",
    minutes: 15,
    due_date: "2026-10-31",
    done: false,
  };
  api.mockImplementation((path, options) =>
    Promise.resolve(
      options
        ? { ...activity, done: JSON.parse(options.body).done }
        : { status: "completed", actions: [activity] },
    ),
  );
  render(<Plan onNavigate={() => {}} />);
  await user.click(
    await screen.findByRole("button", { name: "Mark complete" }),
  );
  expect(
    await screen.findByRole("button", { name: "Completed · Undo" }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(api).toHaveBeenCalledWith(
    "/reports/me/actions/private-id",
    expect.objectContaining({ method: "PATCH" }),
  );
});

test("delete requires explicit confirmation and sends the chosen scope", async () => {
  const user = userEvent.setup(),
    deleted = vi.fn();
  api.mockResolvedValue({ deleted: true });
  render(
    <DeleteDialog open scope="all" onClose={() => {}} onDeleted={deleted} />,
  );
  expect(
    screen.getByRole("dialog", { name: "Delete your diagnostic data?" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Delete my data" })).toBeDisabled();
  await user.type(screen.getByLabelText("Type DELETE to confirm"), "DELETE");
  await user.click(screen.getByRole("button", { name: "Delete my data" }));
  await waitFor(() => expect(deleted).toHaveBeenCalled());
  expect(api).toHaveBeenCalledWith("/reports/me?scope=all", {
    method: "DELETE",
  });
});

test("dashboard fetch failure hides stale figures and offers retry", async () => {
  api.mockRejectedValue(new Error("Offline"));
  render(<Dashboard />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Offline");
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});
