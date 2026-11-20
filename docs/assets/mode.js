/* Bascule élève / parent : retient sur l'appareil la langue choisie en mode parent.
   Rien n'est envoyé. Sans JavaScript, la bascule reste un simple lien. */
(function () {
  "use strict";
  var CLE = "hg:parent-langue";
  var LANGUES = ["fr", "ar", "tr", "en", "es", "pt"];
  function lire() { try { return localStorage.getItem(CLE); } catch (e) { return null; } }
  function ecrire(v) {
    try { if (v) localStorage.setItem(CLE, v); else localStorage.removeItem(CLE); } catch (e) { /* navigation privée */ }
  }

  if (document.body.classList.contains("hg-page--parent")) {
    ecrire(document.documentElement.lang);
  } else {
    var langue = lire();
    if (langue && LANGUES.indexOf(langue) !== -1) {
      document.querySelectorAll('a[data-mode="parent"]').forEach(function (a) {
        a.href = a.href.replace("/parents/fr/", "/parents/" + langue + "/");
      });
      var suite = document.querySelector(".hg-continuer");
      if (suite) suite.hidden = false;
    }
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[data-mode="eleve"]');
    if (a && document.body.classList.contains("hg-page--parent")) ecrire(null);
  });
})();
