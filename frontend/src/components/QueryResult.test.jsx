import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import QueryResult from "../components/QueryResult.jsx";

describe("QueryResult", () => {
  it("does not render rows unless executed is true", () => {
    render(
      <QueryResult
        result={{
          status: "ok",
          executed: false,
          columns: ["secret"],
          rows: [["should-not-show"]],
          row_count: 1,
          sql: "SELECT 1",
          dialect: "postgres",
          assumptions: [],
          warnings: [],
        }}
      />
    );
    expect(screen.queryByText("should-not-show")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renders a table when executed is true", () => {
    render(
      <QueryResult
        result={{
          status: "ok",
          executed: true,
          columns: ["name"],
          rows: [["Asha"]],
          row_count: 1,
          truncated: false,
          sql: "SELECT name FROM customers",
          dialect: "postgres",
          assumptions: ["last month is previous calendar month"],
          explanation: "Top customers",
          warnings: [],
        }}
      />
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("Asha")).toBeInTheDocument();
    expect(screen.getByText("last month is previous calendar month")).toBeInTheDocument();
  });

  it("renders model text as text, not HTML", () => {
    const { container } = render(
      <QueryResult
        result={{
          status: "execution_skipped",
          executed: false,
          sql: "SELECT 1",
          dialect: "mysql",
          assumptions: ["<img src=x onerror=alert(1)>"],
          explanation: "<b>bold</b>",
          warnings: ["<script>alert(1)</script>"],
        }}
      />
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.innerHTML).not.toContain("dangerouslySetInnerHTML");
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(screen.getByText("<b>bold</b>")).toBeInTheDocument();
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
  });
});
