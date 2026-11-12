import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

async function loadDemoLogin(mode: string) {
  vi.resetModules();
  vi.stubEnv("VITE_DEMO_MODE", mode);
  vi.stubEnv("VITE_DEMO_PASSWORD", "DemoPass123!");
  return (await import("./DemoLogin")).default;
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("DemoLogin", () => {
  it("renders nothing outside demo mode", async () => {
    const DemoLogin = await loadDemoLogin("false");
    const { container } = render(<DemoLogin onPick={() => {}} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("explains it is a portfolio demo and links to the source", async () => {
    const DemoLogin = await loadDemoLogin("true");
    render(<DemoLogin onPick={() => {}} />);

    expect(
      screen.getByText(/portfolio demo · not a real company/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /view the source on github/i }),
    ).toHaveAttribute(
      "href",
      "https://github.com/MuhammadHaseeb3112/Multi-Tenant-SaaS-Billing",
    );
    expect(screen.getByText("DemoPass123!")).toBeInTheDocument();
  });

  it("fills in the picked account", async () => {
    const DemoLogin = await loadDemoLogin("true");
    const onPick = vi.fn();
    render(<DemoLogin onPick={onPick} />);

    await userEvent.click(screen.getByRole("button", { name: /owner/i }));

    expect(onPick).toHaveBeenCalledWith("owner@demo.com", "DemoPass123!");
  });
});
