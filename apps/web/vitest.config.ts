import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

/**
 * Unit tests for the pure logic this app's error reporting depends on.
 *
 * Deliberately no DOM environment and no component testing library: everything
 * covered here is a plain function, and keeping it that way is why the
 * diagnostics line was extracted out of the login JSX in the first place.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
