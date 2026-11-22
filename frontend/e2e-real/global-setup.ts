import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { resolve } from "node:path";

const frontendDirectory = process.cwd();
const backendDirectory = resolve(frontendDirectory, "../backend");
const testApiUrl = "http://localhost:8100/api/v1";
const testFrontendUrl = "http://localhost:3101";

function runtimeEnvironment(): NodeJS.ProcessEnv {
  const databaseUrl = process.env.TEST_DATABASE_URL;
  return {
    ...process.env,
    APP_ENVIRONMENT: "test",
    CHAT_PROVIDER: "mock",
    DATABASE_URL: databaseUrl,
    SESSION_TOKEN_HASH_SECRET: "e2e-session-hash-secret-with-at-least-32-characters",
    TEST_DATABASE_URL: databaseUrl,
    TRUSTED_ORIGINS: testFrontendUrl,
  };
}

function run(command: string, args: string[], cwd: string, env: NodeJS.ProcessEnv): void {
  execFileSync(command, args, { cwd, env, stdio: "inherit" });
}

function start(command: string, args: string[], cwd: string, env: NodeJS.ProcessEnv): ChildProcess {
  return spawn(command, args, { cwd, env, stdio: "inherit" });
}

async function waitFor(url: string): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      // The process has not bound its local port yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${url}.`);
}

function stop(process: ChildProcess): void {
  if (!process.killed) process.kill("SIGTERM");
}

export default async function globalSetup() {
  const env = runtimeEnvironment();
  const createdSince = new Date().toISOString();

  // The Python helper parses the URL and requires the exact database name before any command runs.
  run("uv", ["run", "python", "-m", "scripts.e2e_database", "validate"], backendDirectory, env);
  run("uv", ["run", "alembic", "upgrade", "head"], backendDirectory, env);
  run("uv", ["run", "python", "-m", "scripts.e2e_database", "prepare"], backendDirectory, env);
  run(
    "npm",
    ["run", "build", "--", "--webpack"],
    frontendDirectory,
    { ...env, NEXT_PUBLIC_API_URL: testApiUrl },
  );

  const backend = start(
    "uv",
    ["run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8100"],
    backendDirectory,
    env,
  );
  const frontend = start(
    "npm",
    ["run", "start", "--", "--hostname", "127.0.0.1", "--port", "3101"],
    frontendDirectory,
    { ...env, NEXT_PUBLIC_API_URL: testApiUrl },
  );

  await waitFor("http://127.0.0.1:8100/openapi.json");
  await waitFor(testFrontendUrl);

  return async () => {
    stop(frontend);
    stop(backend);
    run(
      "uv",
      ["run", "python", "-m", "scripts.e2e_database", "cleanup", "--created-since", createdSince],
      backendDirectory,
      env,
    );
  };
}
