import { mkdir } from 'node:fs/promises';
import path from 'node:path';

import { chromium } from '/workspaces/chevdev/testscripts/livecook/node_modules/playwright/index.mjs';

const WEB_BASE = process.env.LAB_WEB_BASE_URL || 'http://127.0.0.1:5179';
const BACKEND_BASE = process.env.LAB_SHARED_BACKEND_URL || 'http://127.0.0.1:9001';
const USER_ID = process.env.LAB_CANONICAL_USER_ID || 'demo_user_1';

const SHOT_DIR = '/workspaces/chevdev/interfacetest/session_switch_lab/runtime/screenshots';

async function postJson(pathName, payload) {
  const response = await fetch(`${BACKEND_BASE}${pathName}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`POST ${pathName} failed with ${response.status}`);
  }
  return response.json();
}

async function run() {
  await mkdir(SHOT_DIR, { recursive: true });

  await postJson('/api/session/new', { canonical_user_id: USER_ID });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 980 } });

  await page.goto(WEB_BASE, { waitUntil: 'networkidle' });

  await page.fill('[data-testid="input-chat"]', 'brainstorm about follow restaurants new hashbrown');
  await page.click('[data-testid="button-send"]');

  await page.waitForURL(/\/thread\/\d+/, { timeout: 30000 });
  await page.waitForFunction(
    () => document.body.innerText.includes('Research brief:'),
    { timeout: 30000 },
  );

  await page.screenshot({
    path: path.join(SHOT_DIR, '01_web_research.png'),
    fullPage: true,
  });

  await postJson('/api/chat', {
    canonical_user_id: USER_ID,
    source: 'telegram',
    message: 'Give me a quick recap in one line',
  });

  await page.fill('[data-testid="input-chat"]', 'continue from telegram context');
  await page.click('[data-testid="button-send"]');

  await page.waitForFunction(
    () => document.body.innerText.includes('Continuity note from Telegram context'),
    { timeout: 30000 },
  );

  await page.screenshot({
    path: path.join(SHOT_DIR, '02_web_after_telegram.png'),
    fullPage: true,
  });

  await browser.close();
  console.log(`Screenshots saved in ${SHOT_DIR}`);
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
