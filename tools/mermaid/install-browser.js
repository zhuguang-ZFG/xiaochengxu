const path = require("node:path");
const { execFileSync } = require("node:child_process");

const rootDir = __dirname;

function browserArgs(version, dir = rootDir) {
  return [
    "install",
    `chrome@${version}`,
    "--path",
    path.join(dir, ".browser"),
  ];
}

function main() {
  const version = process.argv[2];
  if (!version) {
    console.error("用法：node install-browser.js <chrome-version>");
    process.exitCode = 2;
    return;
  }
  const cli = path.join(
    path.dirname(require.resolve("@puppeteer/browsers")),
    "main-cli.js",
  );
  execFileSync(process.execPath, [cli, ...browserArgs(version)], {
    stdio: "inherit",
  });
}

if (require.main === module) {
  main();
}

module.exports = { browserArgs };
