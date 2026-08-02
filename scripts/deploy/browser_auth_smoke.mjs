#!/usr/bin/env node
/**
 * Browser smoke: public root must survive automatic Cognito auth handling.
 *
 * Catches the NiceGUI mount-prefix bug where ui.navigate.to("/api/...") becomes
 * /app/api/... and lands on a NiceGUI HTTPException 404 page.
 */
import { chromium } from "playwright";

const base = (process.env.SMOKE_TEST_URL || "http://localhost:8000").replace(/\/$/, "");
const timeoutMs = Number(process.env.BROWSER_SMOKE_TIMEOUT_MS || 20000);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const urls = [];
page.on("framenavigated", (frame) => {
  if (frame === page.mainFrame()) {
    urls.push(frame.url());
  }
});

try {
  await page.goto(`${base}/`, { waitUntil: "domcontentloaded", timeout: timeoutMs });

  // Wait until auth handoff reaches its terminal state or the prefixed-route bug.
  await page.waitForFunction(
    () => {
      const href = location.href;
      if (href.includes("/app/api/v1/auth/login-redirect")) return true;
      if (href.includes("/login") && href.includes("return_url=")) return true;
      return false;
    },
    { timeout: timeoutMs },
  );
  // Give the automatic auth navigate a moment to fire after first paint.
  await page.waitForTimeout(2500);

  const finalUrl = page.url();
  const bodyText = await page.locator("body").innerText();
  const badPrefixed = [...urls, finalUrl].some((u) =>
    u.includes("/app/api/v1/auth/login-redirect"),
  );
  const httpException404 =
    /HTTPException/i.test(bodyText) ||
    (/404/i.test(bodyText) && /Not Found|page/i.test(bodyText) && badPrefixed);
  const finalLocation = new URL(finalUrl);
  const landedOnLogin =
    finalLocation.hostname === "5432wire.com" &&
    /^\/login\/?$/.test(finalLocation.pathname) &&
    finalLocation.searchParams.has("return_url");

  const report = {
    finalUrl,
    urls,
    badPrefixed,
    httpException404,
    landedOnLogin,
    bodySnippet: bodyText.slice(0, 400),
  };
  console.log(JSON.stringify(report, null, 2));

  if (badPrefixed || httpException404) {
    console.error("FAIL: browser navigated to mount-prefixed /app/api/v1/auth/login-redirect");
    process.exit(1);
  }
  if (!landedOnLogin) {
    console.error("FAIL: browser did not reach the 5432wire login handoff with return_url");
    process.exit(1);
  }
  console.log("Browser auth smoke passed.");
} finally {
  await browser.close();
}
