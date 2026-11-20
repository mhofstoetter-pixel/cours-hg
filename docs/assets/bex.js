/* Pages BEX interactives : cartes méthode, critères à cocher, modelage pas à pas,
   exercices « faits », sommaire collant. Rien n'est envoyé : la progression reste
   dans le navigateur de l'élève (localStorage, si disponible). */
(function () {
  "use strict";
  var racine = document.querySelector(".bex");
  if (!racine) return;
  document.documentElement.classList.add("bex-js");

  var prefixe = "bex:" + location.pathname + ":";
  function lire(cle) {
    try { return localStorage.getItem(prefixe + cle); } catch (e) { return null; }
  }
  function ecrire(cle, valeur) {
    try {
      if (valeur === null) localStorage.removeItem(prefixe + cle);
      else localStorage.setItem(prefixe + cle, valeur);
    } catch (e) { /* navigation privée : on continue sans mémoire */ }
  }
  var mouvementReduit = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------- Cartes méthode */
  racine.querySelectorAll(".bex-cartes").forEach(function (groupe) {
    var faces = Array.prototype.slice.call(groupe.querySelectorAll(".bex-carte__face"));
    var tout = groupe.querySelector(".bex-cartes__tout");
    function regler(face, ouvert) {
      face.setAttribute("aria-expanded", ouvert ? "true" : "false");
      var dos = document.getElementById(face.getAttribute("aria-controls"));
      if (dos) dos.hidden = !ouvert;
    }
    function majTout() {
      if (!tout) return;
      var toutesOuvertes = faces.every(function (f) { return f.getAttribute("aria-expanded") === "true"; });
      tout.textContent = toutesOuvertes ? "Cacher toutes les réponses" : "Retourner toutes les cartes";
    }
    faces.forEach(function (face) {
      regler(face, false);
      face.addEventListener("click", function () {
        regler(face, face.getAttribute("aria-expanded") !== "true");
        majTout();
      });
    });
    if (tout) {
      tout.hidden = false;
      tout.addEventListener("click", function () {
        var ouvrir = faces.some(function (f) { return f.getAttribute("aria-expanded") !== "true"; });
        faces.forEach(function (f) { regler(f, ouvrir); });
        majTout();
      });
      majTout();
    }
  });

  /* ---------------------------------------------------- Critères à cocher */
  racine.querySelectorAll(".bex-criteres").forEach(function (bloc) {
    var cases = Array.prototype.slice.call(bloc.querySelectorAll('input[type="checkbox"]'));
    var bilan = bloc.querySelector(".bex-criteres__bilan");
    var effacer = bloc.querySelector(".bex-criteres__effacer");
    function maj() {
      var n = cases.filter(function (c) { return c.checked; }).length;
      if (bilan) {
        bilan.textContent = n === 0 ? "" :
          n === cases.length ? "Tous les critères sont réussis. Bravo !" :
          n + " critère" + (n > 1 ? "s" : "") + " réussi" + (n > 1 ? "s" : "") + " sur " + cases.length + ".";
      }
      if (effacer) effacer.hidden = n === 0;
    }
    cases.forEach(function (c) {
      if (lire(c.id) === "1") c.checked = true;
      c.addEventListener("change", function () { ecrire(c.id, c.checked ? "1" : null); maj(); });
    });
    if (effacer) effacer.addEventListener("click", function () {
      cases.forEach(function (c) { c.checked = false; ecrire(c.id, null); });
      maj();
      if (cases[0]) cases[0].focus();
    });
    maj();
  });

  /* ---------------------------------------------------- Modelage pas à pas */
  racine.querySelectorAll(".bex-pas").forEach(function (liste) {
    var etapes = Array.prototype.slice.call(liste.querySelectorAll(":scope > .bex-pas__etape"));
    if (etapes.length < 2) return;
    var montrees = 1;
    etapes.forEach(function (e, i) { e.hidden = i > 0; e.setAttribute("tabindex", "-1"); });

    var commandes = document.createElement("div");
    commandes.className = "bex-pas__commandes";
    var suivant = document.createElement("button");
    suivant.type = "button";
    suivant.className = "bex-bouton";
    var compte = document.createElement("span");
    compte.className = "bex-pas__compte";
    compte.setAttribute("aria-live", "polite");
    var toutes = document.createElement("button");
    toutes.type = "button";
    toutes.className = "bex-lien";
    toutes.textContent = "Tout afficher";
    commandes.appendChild(suivant);
    commandes.appendChild(compte);
    commandes.appendChild(toutes);
    liste.parentNode.insertBefore(commandes, liste.nextSibling);

    function maj() {
      compte.textContent = "Étape " + montrees + " sur " + etapes.length;
      suivant.innerHTML = 'Étape suivante <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" ' +
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>';
      if (montrees >= etapes.length) commandes.remove();
    }
    function montrer(e) {
      e.hidden = false;
      if (!mouvementReduit) {
        e.classList.add("est-nouvelle");
        e.addEventListener("animationend", function () { e.classList.remove("est-nouvelle"); }, { once: true });
      }
    }
    suivant.addEventListener("click", function () {
      var e = etapes[montrees];
      if (!e) return;
      montrer(e);
      montrees += 1;
      maj();
      e.focus({ preventScroll: true });
      e.scrollIntoView({ behavior: mouvementReduit ? "auto" : "smooth", block: "start" });
    });
    toutes.addEventListener("click", function () {
      etapes.forEach(function (e) { if (e.hidden) montrer(e); });
      montrees = etapes.length;
      var premiere = etapes[1];
      maj();
      if (premiere) premiere.focus({ preventScroll: true });
    });
    maj();
  });

  /* ---------------------------------------------------- Exercices faits + progression */
  var progression = racine.querySelector(".bex-progression");
  var exercices = Array.prototype.slice.call(racine.querySelectorAll(".bex-exercice"));
  var cases = [];
  if (progression && exercices.length) {
    var texte = document.createElement("span");
    var rangee = document.createElement("span");
    rangee.className = "bex-progression__cases";
    rangee.setAttribute("aria-hidden", "true");
    exercices.forEach(function () {
      var c = document.createElement("span");
      c.className = "bex-progression__case";
      rangee.appendChild(c);
      cases.push(c);
    });
    progression.appendChild(rangee);
    progression.appendChild(texte);
    progression.hidden = false;
  } else if (progression) {
    progression.hidden = true;
  }
  function majProgression() {
    var n = 0;
    exercices.forEach(function (ex, i) {
      var fait = ex.classList.contains("est-fait");
      if (fait) n += 1;
      if (cases[i]) cases[i].classList.toggle("est-fait", fait);
    });
    if (progression && progression.lastChild) {
      var total = exercices.length;
      progression.lastChild.textContent =
        n === 0 ? total + (total > 1 ? " exercices à faire" : " exercice à faire") :
        n === total ? (total > 1 ? "Tous les exercices sont faits" : "Exercice fait") :
        n + (n > 1 ? " exercices faits" : " exercice fait") + " sur " + total;
    }
  }
  exercices.forEach(function (ex) {
    var c = ex.querySelector('.bex-fait input[type="checkbox"]');
    if (!c) return;
    if (lire(c.id) === "1") { c.checked = true; ex.classList.add("est-fait"); }
    c.addEventListener("change", function () {
      ecrire(c.id, c.checked ? "1" : null);
      ex.classList.toggle("est-fait", c.checked);
      majProgression();
    });
  });
  majProgression();

  /* ---------------------------------------------------- Sommaire collant */
  var sommaire = racine.querySelector(".bex-sommaire");
  if (!sommaire) return;
  function hauteurSommaire() {
    racine.style.setProperty("--bex-sticky", sommaire.offsetHeight + "px");
  }
  hauteurSommaire();
  window.addEventListener("resize", hauteurSommaire);

  var liens = Array.prototype.slice.call(sommaire.querySelectorAll("a[href^='#']"));
  var parId = {};
  liens.forEach(function (a) { parId[a.getAttribute("href").slice(1)] = a; });
  var courant = null;
  function activer(id) {
    if (id === courant || !parId[id]) return;
    courant = id;
    liens.forEach(function (a) { a.removeAttribute("aria-current"); });
    var a = parId[id];
    a.setAttribute("aria-current", "true");
    var ol = a.closest("ol");
    if (ol && ol.scrollWidth > ol.clientWidth) {
      var gauche = a.offsetLeft - ol.offsetLeft;
      var droite = gauche + a.offsetWidth;
      if (gauche < ol.scrollLeft || droite > ol.scrollLeft + ol.clientWidth) {
        ol.scrollTo({ left: Math.max(0, gauche - 16), behavior: mouvementReduit ? "auto" : "smooth" });
      }
    }
  }
  var sections = Array.prototype.slice.call(racine.querySelectorAll(".bex-partie"));
  function surDefilement() {
    var limite = sommaire.offsetHeight + 24;
    var actif = sections[0];
    sections.forEach(function (s) { if (s.getBoundingClientRect().top - limite <= 0) actif = s; });
    if (actif) activer(actif.id);
  }
  var attente = false;
  window.addEventListener("scroll", function () {
    if (attente) return;
    attente = true;
    requestAnimationFrame(function () { attente = false; surDefilement(); });
  }, { passive: true });
  surDefilement();
})();
