// A minimal Language Server Protocol client that talks to the JSONiq language server over stdio,
// as an editor does. It supports requests, notifications, and waiting for published diagnostics.
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

// The language server and RumbleDB are expected next to this repository, as in the other benchmarks.
export const SERVER = join(import.meta.dirname, "..", "..", "jsoniq-lsp", "packages", "language-server", "dist", "main.mjs");

/**
 * Reads the arguments `<on|off> <out.json>` of a benchmark script (on/off: RumbleDB wrapper), and creates the
 * folder of the output file. Exits with the usage if they are missing, so that a long run cannot fail at the end.
 */
export function parseArgs(script) {
    const [configuration, outPath] = process.argv.slice(2);
    if (!["on", "off"].includes(configuration) || !outPath) {
        console.error(`Usage: node ${script} <on|off> <out.json>`);
        process.exit(1);
    }
    mkdirSync(dirname(outPath), { recursive: true });
    return { wrapper: configuration === "on", outPath };
}

export class LspClient {
    /**
     * @param rootPath  workspace folder reported to the server
     * @param wrapper   whether the server may start the RumbleDB wrapper (Java)
     * @param cwd       working directory of the server; the wrapper writes Spark files there
     */
    constructor({ rootPath, wrapper, cwd = join(import.meta.dirname, "data", "server-cwd") }) {
        mkdirSync(cwd, { recursive: true });
        // SERVER_NODE_ARGS passes extra flags to Node, for example --cpu-prof for profiling.
        const nodeArgs = process.env.SERVER_NODE_ARGS ? process.env.SERVER_NODE_ARGS.split(" ") : [];
        this.proc = spawn(process.execPath, [...nodeArgs, SERVER, "--stdio"], { cwd, stdio: ["pipe", "pipe", "pipe"] });
        this.proc.stderr.on("data", () => {});
        this.proc.stdout.on("data", (chunk) => this.#onData(chunk));

        this.rootPath = rootPath;
        this.wrapper = wrapper;
        this.buffer = Buffer.alloc(0);
        this.nextId = 1;
        this.version = 0; // document version, increased by every open and change
        this.pendingRequests = new Map(); // id -> { resolve, reject }
        this.diagnosticWaiters = new Map(); // uri -> callback for the next publishDiagnostics
    }

    async start() {
        const rootUri = pathToFileURL(this.rootPath).href;
        await this.request("initialize", {
            processId: process.pid,
            rootUri,
            workspaceFolders: [{ uri: rootUri, name: "root" }],
            capabilities: {
                textDocument: { publishDiagnostics: {}, completion: { completionItem: { snippetSupport: true } } },
                workspace: { workspaceFolders: true, configuration: true },
            },
            initializationOptions: { wrapper: { enabled: this.wrapper } },
        });
        this.notify("initialized", {});
    }

    async stop() {
        await Promise.race([this.request("shutdown", null), new Promise((r) => setTimeout(r, 5000))]);
        this.notify("exit", null);
        setTimeout(() => this.proc.kill("SIGKILL"), 2000).unref();
    }

    request(method, params) {
        const id = this.nextId++;
        return new Promise((resolve, reject) => {
            this.pendingRequests.set(id, { resolve, reject });
            this.#send({ jsonrpc: "2.0", id, method, params });
        });
    }

    notify(method, params) {
        this.#send({ jsonrpc: "2.0", method, params });
    }

    open(uri, text, languageId = "jsoniq") {
        this.notify("textDocument/didOpen", { textDocument: { uri, languageId, version: ++this.version, text } });
    }

    /** Replaces the whole text of an open document. */
    change(uri, text) {
        this.notify("textDocument/didChange", { textDocument: { uri, version: ++this.version }, contentChanges: [{ text }] });
    }

    close(uri) {
        this.notify("textDocument/didClose", { textDocument: { uri } });
    }

    /** Resolves with the next diagnostics published for `uri`, or with null after `timeoutMs`. */
    nextDiagnostics(uri, timeoutMs = 600_000) {
        return new Promise((resolve) => {
            const timer = setTimeout(() => {
                this.diagnosticWaiters.delete(uri);
                resolve(null);
            }, timeoutMs);
            this.diagnosticWaiters.set(uri, (diagnostics) => {
                clearTimeout(timer);
                resolve(diagnostics);
            });
        });
    }

    // Messages are framed as "Content-Length: n\r\n\r\n" followed by n bytes of JSON.
    #send(message) {
        const body = Buffer.from(JSON.stringify(message), "utf8");
        this.proc.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
        this.proc.stdin.write(body);
    }

    #onData(chunk) {
        this.buffer = Buffer.concat([this.buffer, chunk]);
        for (;;) {
            const headerEnd = this.buffer.indexOf("\r\n\r\n");
            if (headerEnd < 0) return;
            const length = Number(/Content-Length: (\d+)/i.exec(this.buffer.subarray(0, headerEnd).toString("ascii"))[1]);
            const bodyStart = headerEnd + 4;
            if (this.buffer.length < bodyStart + length) return;
            const message = JSON.parse(this.buffer.subarray(bodyStart, bodyStart + length).toString("utf8"));
            this.buffer = this.buffer.subarray(bodyStart + length);
            this.#onMessage(message);
        }
    }

    #onMessage(message) {
        const isResponse = message.id !== undefined && message.method === undefined;
        const isServerRequest = message.id !== undefined && message.method !== undefined;

        if (isResponse) {
            const pending = this.pendingRequests.get(message.id);
            this.pendingRequests.delete(message.id);
            if (message.error) pending?.reject(new Error(message.error.message));
            else pending?.resolve(message.result);
        } else if (isServerRequest) {
            // The server asks for configuration or registers capabilities: answer with defaults.
            const result = message.method === "workspace/configuration" ? [] : null;
            this.#send({ jsonrpc: "2.0", id: message.id, result });
        } else if (message.method === "textDocument/publishDiagnostics") {
            const waiter = this.diagnosticWaiters.get(message.params.uri);
            this.diagnosticWaiters.delete(message.params.uri);
            waiter?.(message.params.diagnostics);
        }
    }
}
