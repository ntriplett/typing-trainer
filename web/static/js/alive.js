// Tells the server a page is still open. The installed app shuts its
// server down a few minutes after the last ping (app/desktop.py); in dev
// the ping does nothing.
setInterval(() => fetch("/api/alive", { method: "POST" }).catch(() => {}), 30000);
