import { useState } from "react";
import { LogIn } from "lucide-react";

function LoginPage() {
  const [status, setStatus] = useState("● Ready");

  const handleLogin = (e) => {
    e.preventDefault();
    setStatus("● Authenticating...");
    setTimeout(() => {
      setStatus("● Success");
    }, 1000);
  };

  return (
    <div style={styles.app}>
      {/* Top Bar */}
      <div style={styles.topBar}>
        <span style={styles.brand}>SRaaS</span>
        <span style={styles.status}>{status}</span>
      </div>

      {/* Center Card */}
      <div style={styles.center}>
        <div style={styles.card}>
          <div style={styles.header}>
            <h2 style={styles.title}>Authentication</h2>
            <p style={styles.subtitle}>P0.0 Login</p>
          </div>

          <form onSubmit={handleLogin} style={styles.form}>
            <div style={styles.inputGroup}>
              <label style={styles.label}>Username</label>
              <input
                type="text"
                placeholder="Enter username"
                style={styles.input}
                required
              />
            </div>

            <div style={styles.inputGroup}>
              <label style={styles.label}>Password</label>
              <input
                type="password"
                placeholder="Enter password"
                style={styles.input}
                required
              />
            </div>

            <button type="submit" style={styles.button}>
              <LogIn size={16} />
              <span>Login</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;

const styles = {
  app: {
    height: "100vh",
    backgroundColor: "#0f0f0f",
    color: "#fff",
    fontFamily: "monospace",
    display: "flex",
    flexDirection: "column",
  },

  topBar: {
    height: "42px",
    display: "flex",
    alignItems: "center",
    padding: "0 16px",
    backgroundColor: "#1e1e1e",
    borderBottom: "1px solid #333",
  },

  brand: {
    color: "#2ea043",
    fontWeight: "bold",
    fontSize: "14px",
  },

  status: {
    marginLeft: "auto",
    fontSize: "13px",
    color: "#2ea043",
  },

  center: {
    flex: 1,
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },

  card: {
    width: "320px",
    padding: "20px 24px",
    backgroundColor: "#1e1e1e",
    border: "1px solid #333",
    borderRadius: "12px",
  },

  header: {
    marginBottom: "16px",
  },

  title: {
    fontSize: "16px",
    fontWeight: "bold",
    color: "#fff",
    margin: 0,
  },

  subtitle: {
    fontSize: "12px",
    color: "#888",
    margin: 0,
    marginTop: "2px",
  },

  form: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },

  inputGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },

  label: {
    fontSize: "12px",
    color: "#aaa",
    fontWeight: "500",
  },

  input: {
    padding: "8px 10px",
    borderRadius: "6px",
    border: "1px solid #333",
    fontFamily: "monospace",
    fontSize: "13px",
    backgroundColor: "#0f0f0f",
    color: "#fff",
    outline: "none",
  },

  button: {
    marginTop: "4px",
    padding: "8px 14px",
    borderRadius: "6px",
    border: "none",
    backgroundColor: "#2ea043",
    color: "#fff",
    fontWeight: "bold",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "6px",
    fontSize: "13px",
  },
};