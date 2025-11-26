//utils/serviceChecker.js 

const util = require('util');
const exec = util.promisify(require('child_process').exec);
const config = require('../config/env');

// --- STATE ---
// This variable is updated in the background.
// The API reads this instantly.
let isServiceRunning = false; 

// --- BACKGROUND WORKER ---
const updateServiceStatus = async () => {
  try {
    // Check if Python process is running
    // -NoProfile: Faster startup
    // -NonInteractive: Safer
    const { stdout } = await exec(
      `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \\"Name like 'python%'\\" | Where-Object { $_.CommandLine -match 'sylvac_reader.py' } | Select-Object -First 1 ProcessId"`
    );
    
    isServiceRunning = stdout.trim().length > 0;
  } catch (err) {
    isServiceRunning = false;
  } finally {
    // Re-check in 3 seconds
    setTimeout(updateServiceStatus, 3000);
  }
};

// Start the worker immediately
updateServiceStatus();

// --- EXPORTS ---

// 1. Instant Synchronous Getter (For the Controller)
function getRunningState() {
  return isServiceRunning;
}

// 2. Legacy Start/Stop (Keep these async as they are user actions)
async function run(cmd) {
  return exec(cmd, { windowsHide: true });
}

async function start() {
  const name = config.pyServiceName;
  try { await run(`nssm start ${name}`); }
  catch { await run(`sc start "${name}"`); }
  // Force an immediate update after action
  setTimeout(updateServiceStatus, 1000);
  return true;
}

async function stop() {
  const name = config.pyServiceName;
  try { await run(`nssm stop ${name}`); }
  catch { await run(`sc stop "${name}"`); }
  setTimeout(updateServiceStatus, 1000);
  return false;
}

module.exports = { getRunningState, start, stop };