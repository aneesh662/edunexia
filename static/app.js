// Discourage casual copying; these controls are not a security boundary.
document.addEventListener("contextmenu", function(e) {
  if (e.target.closest(".protected-content, video, iframe")) e.preventDefault();
});
document.addEventListener("keydown", function(e) {
  const protectedTarget = e.target.closest && e.target.closest(".protected-content");
  if (protectedTarget && (e.ctrlKey || e.metaKey) && ["s","p","u"].includes(e.key.toLowerCase())) {
    e.preventDefault();
  }
});