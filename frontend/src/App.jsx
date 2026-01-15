import { useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";
import { Play } from "lucide-react";

function App() {
  const [code, setCode] = useState(
`print("Hello SRaaS")
print("Editor + Terminal UI")`
  );

  const [output, setOutput] = useState("$ Ready\n");

  const runCode = () => {
    // TEMP: frontend-only mock
    setOutput(
      `$ Running Python...\n` +
      `Hello SRaaS\n` +
      `Editor + Terminal UI\n`
    );
  };

  return (
    <div style={styles.app}>
      
      {/* TOP BAR */}
      <div style={styles.topBar}>
        <button style={styles.runBtn} onClick={runCode}>
          <Play size={16} /> Run
        </button>

        <span style={styles.lang}>Python</span>
        <span style={styles.status}>● Ready</span>
      </div>

      {/* EDITOR */}
      <div style={styles.editor}>
        <CodeMirror
          value={code}
          extensions={[python()]}
          theme={oneDark}
          onChange={(v) => setCode(v)}
          height="100%"
          width="100%"
        />
      </div>

      {/* TERMINAL */}
      <div style={styles.terminal}>
        <pre>{output}</pre>
      </div>
    </div>
  );
}

export default App;

const styles = {
  app: {
    height: "100vh",
    width: "100vw",
    display: "flex",
    flexDirection: "column",
    backgroundColor: "#0f0f0f",
    color: "#fff",
    fontFamily: "monospace",
  },
  topBar: {
    height: "42px",
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "0 12px",
    backgroundColor: "#1e1e1e",
    borderBottom: "1px solid #333",
  },
  runBtn: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    background: "#2ea043",
    border: "none",
    color: "#fff",
    padding: "6px 12px",
    cursor: "pointer",
    borderRadius: "4px",
    fontWeight: "bold",
  },
  lang: {
    fontSize: "14px",
    opacity: 0.8,
  },
  status: {
    marginLeft: "auto",
    fontSize: "13px",
    color: "#2ea043",
  },
  editor: {
    flex: 1,
  },
  terminal: {
    height: "25vh",
    backgroundColor: "#0b0b0b",
    borderTop: "1px solid #333",
    padding: "10px",
    overflowY: "auto",
    fontSize: "14px",
  },
};
