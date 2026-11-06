import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("renders the synthetic demonstration disclosure", () => {
    render(<HomePage />);

    expect(screen.getByRole("heading", { name: "AI Supply Assistant" })).toBeInTheDocument();
    expect(screen.getByText(/synthetic-data portfolio demonstration/i)).toBeInTheDocument();
  });
});
