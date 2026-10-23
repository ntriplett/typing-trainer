// Walking-skeleton wiring: fetch the one activity we have and render it.
// Replaced by real activity rendering once the scheduler/module contract
// (PLAN.md Section 7) has more than one activity to show.

async function loadHelloWorldActivity() {
  const el = document.getElementById("activity-message");
  try {
    const res = await fetch("/api/activities/hello-world");
    if (!res.ok) {
      throw new Error(`Request failed: ${res.status}`);
    }
    const data = await res.json();
    el.textContent = data.message;
  } catch (err) {
    el.textContent = "Could not reach the server.";
    console.error(err);
  }
}

loadHelloWorldActivity();
