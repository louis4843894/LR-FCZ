"use client";

/** Always present in the root layout; browser APIs run only on activation. */
export function SkipNavigation() {
  function focusMain() {
    const main = document.querySelector("main");
    if (!main) return;
    main.tabIndex = -1;
    main.focus({ preventScroll: true });
    main.scrollIntoView({ block: "start" });
  }

  return <button type="button" className="skip-navigation" onClick={focusMain}>跳至主要內容</button>;
}
