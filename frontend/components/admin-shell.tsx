"use client";

import Link from "next/link";
import { ReactNode } from "react";

type AdminShellProps = {
  activeSection: "faqs" | "debug" | "escalations";
  title: string;
  description: string;
  children: ReactNode;
};

export function AdminShell({
  activeSection,
  title,
  description,
  children
}: AdminShellProps) {
  return (
    <main className="appShell adminAppShell">
      <header className="topBar adminTopBar">
        <div>
          <span className="sectionTag">Admin</span>
          <h1 className="pageTitle">{title}</h1>
          <p className="subtleText">{description}</p>
        </div>
        <nav aria-label="Admin navigation" className="adminNav">
          <Link
            className={`navLink ${activeSection === "faqs" ? "active" : ""}`}
            href="/admin"
          >
            FAQ
          </Link>
          <Link
            className={`navLink ${activeSection === "debug" ? "active" : ""}`}
            href="/admin/debug"
          >
            Retrieval Debug
          </Link>
          <Link
            className={`navLink ${activeSection === "escalations" ? "active" : ""}`}
            href="/admin/escalations"
          >
            Escalations
          </Link>
        </nav>
      </header>

      {children}
    </main>
  );
}
