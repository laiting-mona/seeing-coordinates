// Site settings for the trial. Leave endpoint empty to turn logging off.
// Last edited: 2026-11-18: endpoint '/' sends logs to the same Worker that serves the site (POST /log).
window.SC_CONFIG = {
  endpoint: '/',           // '/' = this site's own Worker; '' turns logging (and the consent notice) off
  formUrl: '',             // Google Form link for feedback; the button is hidden while this is empty
  retention: '2027-01-31', // date shown in the consent notice; online records are deleted after it
};
