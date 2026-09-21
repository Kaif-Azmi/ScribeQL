import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: "2rem", maxWidth: 480, margin: "0 auto" }}>
          <h1>Something went wrong</h1>
          <p style={{ color: "var(--text-secondary)", marginTop: "0.75rem" }}>
            Reload the page to continue. If it keeps happening, include any request ID from
            the last error when you report it.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              marginTop: "1.25rem",
              background: "var(--accent)",
              color: "#fff",
              border: 0,
              borderRadius: 8,
              padding: "0.5rem 1rem",
              cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
