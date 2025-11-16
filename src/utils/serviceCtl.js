// const { exec } = require('child_process');
const config = require('../config/env');
const util = require('util');
// const exec = util.promisify(require('child_process').exec);

const exec = util.promisify(require('child_process').exec);

function run(cmd) {
  return new Promise((resolve, reject) => {
    exec(cmd, { windowsHide: true }, (err, stdout, stderr) => {
      if (err) return reject({ err, stdout, stderr });
      resolve({ stdout, stderr });
    });
  });
}

// async function isRunning() {
//   const name = config.pyServiceName;
//   try {
//     const { stdout } = await run(`nssm status ${name}`);
//     return stdout.toLowerCase().includes('running');
//   } catch {
//     try {
//       const { stdout } = await run(`sc query "${name}"`);
//       return /STATE\s*:\s*4\s+RUNNING/i.test(stdout);
//     } catch { return false; }
//   }
// }





async function isRunning() {
  try {
    const { stdout } = await exec(
      `powershell -NoProfile -ExecutionPolicy Bypass -Command `
      + `"Get-CimInstance Win32_Process `
      + `| Where-Object { `
      + `($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') `
      + `-and $_.CommandLine -match 'sylvac_reader.py' `
      + `} `
      + `| Select-Object -ExpandProperty ProcessId"`
    );

    const output = Buffer.isBuffer(stdout) ? stdout.toString() : stdout;

    // If any PID exists → running
    return output.trim().length > 0;
  } catch (err) {
    console.error("isRunning() ERROR:", err);
    return false;
  }
}



async function start() {
  const name = config.pyServiceName;
  try { await run(`nssm start ${name}`); }
  catch { await run(`sc start "${name}"`); }
  await new Promise(r => setTimeout(r, 800));
  return isRunning();
}

async function stop() {
  const name = config.pyServiceName;
  try { await run(`nssm stop ${name}`); }
  catch { await run(`sc stop "${name}"`); }
  await new Promise(r => setTimeout(r, 800));
  return isRunning();
}

module.exports = { isRunning, start, stop };