import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App from "./App";


describe("guest home page", () => {
  it("presents quick parking as the primary action", () => {
    render(<BrowserRouter><App /></BrowserRouter>);

    expect(screen.getByRole("heading", { name: "Your spot is ready when you are." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Park now" })).toHaveAttribute("href", "/quick");
    expect(screen.getByRole("link", { name: "Book in advance" })).toHaveAttribute("href", "/book");
  });
});

