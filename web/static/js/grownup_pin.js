// Choosing the grown-ups' PIN: on first run (welcome.js), or on the For Grown-ups page.
// choosePinForm(box, {title, onDone}) fills `box` with the form.

function choosePinForm(box, { title, intro, onDone }) {
  box.innerHTML = `
    <h2 class="panel-title">${title}</h2>
    <p class="parent-intro">${intro}</p>
    <form class="pin-form">
      <label>New PIN <input class="pin-input pin-one" type="password" inputmode="numeric" maxlength="4" autocomplete="new-password" /></label>
      <label>Type it again <input class="pin-input pin-two" type="password" inputmode="numeric" maxlength="4" autocomplete="new-password" /></label>
      <button type="submit" class="button-go">Save PIN</button>
    </form>
    <p class="error-text pin-message" role="status"></p>`;
  const one = box.querySelector(".pin-one");
  const message = box.querySelector(".pin-message");
  one.focus();
  box.querySelector(".pin-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    message.textContent = "";
    if (one.value !== box.querySelector(".pin-two").value) {
      message.textContent = "Those don't match. Try again.";
      return;
    }
    const res = await fetch("/api/grownups/pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: one.value }),
    });
    if (!res.ok) {
      message.textContent = (await res.json()).detail || "That PIN didn't work.";
      return;
    }
    onDone();
  });
}
