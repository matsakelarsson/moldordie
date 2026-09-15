/* Project specific Javascript goes here. Scripts live in files like this one, never in templates:
   the Content Security Policy allows no inline code. Listen on the document so that markup htmx
   swaps in later needs no new listeners. */

// Dismiss an alert (templates/cotton/ui/alert.html) from its data-ui-dismiss button.
document.addEventListener('click', (event) => {
  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }
  const dismiss = target.closest('[data-ui-dismiss]');
  if (dismiss === null) {
    return;
  }
  const alert = dismiss.closest('[data-ui-alert]');
  if (alert !== null) {
    alert.remove();
  }
});
