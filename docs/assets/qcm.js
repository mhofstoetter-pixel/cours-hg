/*
 * qcm.js — moteur d'entraînement aux QCM du site HG (voir CONTRATS.md §2 et §3).
 * Sans dépendance, ES2017, fichier unique.
 * Rien n'est envoyé ni enregistré hors du navigateur : seul le meilleur score
 * peut être gardé dans localStorage (dans un try/catch).
 *
 * Utilisation : <div id="qcm" data-src="qcm.json" data-retour="../../"></div>
 *               <script src="../../../assets/qcm.js" defer></script>
 * data-retour est facultatif (défaut : "../../", la page du niveau).
 */
(function () {
  'use strict';

  /* ---------- Petits outils ---------- */

  var compteur = 0;
  function uid(prefixe) { compteur += 1; return 'qcm-' + prefixe + '-' + compteur; }

  function el(tag, classe, html) {
    var n = document.createElement(tag);
    if (classe) n.className = classe;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function texteEl(tag, classe, texte) {
    var n = document.createElement(tag);
    if (classe) n.className = classe;
    n.textContent = texte;
    return n;
  }

  function melange(liste) {
    var a = liste.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  function fraction(x) {
    var f = Number(x);
    return isFinite(f) ? f : 0;
  }

  function borne(x) { return Math.max(0, Math.min(1, x)); }

  /* Comparaison des réponses libres : sans casse, espaces superflus ni différence d'apostrophe. */
  function normalise(s) {
    var t = String(s == null ? '' : s);
    if (t.normalize) t = t.normalize('NFC');
    return t.replace(/[’‘ʼ`]/g, "'").replace(/\s+/g, ' ').trim().toLowerCase();
  }

  /* Réponse courte Moodle : « * » est un joker. */
  function correspond(saisie, attendu) {
    var a = normalise(attendu);
    var s = normalise(saisie);
    if (a.indexOf('*') === -1) return s === a;
    var motif = a.split('*').map(function (m) {
      return m.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('.*');
    return new RegExp('^' + motif + '$').test(s);
  }

  /* Texte brut d'un fragment HTML, sans charger ses images (template inerte). */
  function texteSeul(html) {
    var t = document.createElement('template');
    t.innerHTML = String(html || '').replace(/\{\{\d+\}\}/g, '…');
    return (t.content.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function nombre(x) {
    var r = Math.round(x * 10) / 10;
    return String(r).replace('.', ',');
  }

  function abrege(s, max) {
    return s.length > max ? s.slice(0, max - 1).replace(/\s+\S*$/, '') + '…' : s;
  }

  var ICONES = {
    juste: '<path d="M4.5 12.5l4.5 4.5L19.5 7"/>',
    faux: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    partiel: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/>'
  };

  function icone(etat) {
    return '<svg class="qcm-icone" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false" ' +
      'fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">' +
      ICONES[etat] + '</svg>';
  }

  /* Pastille « icône + mot » : le juste/faux n'est jamais signalé par la seule couleur. */
  function marque(etat, mot) {
    var m = el('span', 'qcm-marque qcm-marque--' + etat, icone(etat));
    m.appendChild(texteEl('span', null, mot));
    return m;
  }

  function etatDe(score, toutJuste) {
    if (toutJuste) return 'juste';
    return score > 0 ? 'partiel' : 'faux';
  }

  var VERDICTS = { juste: 'Juste !', partiel: 'Partiellement juste', faux: 'À revoir' };
  var ETATS_COURTS = { juste: 'juste', partiel: 'partiellement juste', faux: 'à revoir' };

  /* ---------- Types de questions ----------
   * Chaque fonction reçoit (question, contexte) et renvoie :
   *   { noeud, manque() -> message|null, corriger() -> { score, etat, feedbacks: [noeud] } }
   */

  function rendreChoix(q, ctx) {
    var multiple = !!q.multiple;
    var reponses = q.melanger === false ? q.reponses.slice() : melange(q.reponses);
    var court = reponses.every(function (r) { return texteSeul(r.texteHtml).length <= 14; });

    var groupe = el('fieldset', 'qcm-options' + (court ? ' qcm-options--court' : ''));
    groupe.setAttribute('aria-labelledby', ctx.idEnonce + ' ' + ctx.idConsigne);
    var nom = uid('choix');

    var items = reponses.map(function (r) {
      var label = el('label', 'qcm-option');
      var input = document.createElement('input');
      input.type = multiple ? 'checkbox' : 'radio';
      input.name = nom;
      input.className = 'qcm-option__case';
      var texte = el('span', 'qcm-option__texte', r.texteHtml);
      label.appendChild(input);
      label.appendChild(texte);
      groupe.appendChild(label);
      return { r: r, input: input, label: label };
    });

    function majCoches() {
      items.forEach(function (it) { it.label.classList.toggle('est-coche', it.input.checked); });
    }
    groupe.addEventListener('change', majCoches);

    return {
      noeud: groupe,
      manque: function () {
        if (items.some(function (it) { return it.input.checked; })) return null;
        items[0].input.focus();
        return multiple ? 'Cochez au moins une réponse avant de vérifier.' : 'Choisissez une réponse avant de vérifier.';
      },
      corriger: function () {
        var coches = items.filter(function (it) { return it.input.checked; });
        var somme = coches.reduce(function (s, it) { return s + fraction(it.r.fraction); }, 0);
        var negatif = coches.some(function (it) { return fraction(it.r.fraction) < 0; });
        var score = borne(somme);
        var toutJuste = multiple ? (somme >= 0.999 && !negatif) : somme >= 0.999;
        if (multiple && negatif) score = Math.min(score, 0.999);

        var feedbacks = [];
        items.forEach(function (it) {
          var f = fraction(it.r.fraction);
          it.input.disabled = true;
          it.label.classList.add('est-corrige');
          if (it.input.checked) {
            var etat = f >= 0.999 || (multiple && f > 0) ? 'juste' : (f > 0 ? 'partiel' : 'faux');
            var mot = etat === 'juste' ? 'Juste' : (etat === 'partiel' ? 'En partie juste' : 'Erreur');
            it.label.classList.add('qcm-option--' + etat);
            it.label.appendChild(marque(etat, mot));
            if (it.r.feedbackHtml) feedbacks.push(el('div', 'qcm-feedback__item', it.r.feedbackHtml));
          } else if (f > 0) {
            it.label.classList.add('qcm-option--attendue');
            it.label.appendChild(marque('juste', 'Bonne réponse'));
          }
        });
        return { score: score, etat: etatDe(score, toutJuste), feedbacks: feedbacks };
      }
    };
  }

  function creerSelect(choix, idLabel, etiquette) {
    var select = document.createElement('select');
    select.className = 'qcm-select';
    if (idLabel) select.id = idLabel;
    if (etiquette) select.setAttribute('aria-label', etiquette);
    var vide = document.createElement('option');
    vide.value = '';
    vide.textContent = 'Choisissez…';
    select.appendChild(vide);
    choix.forEach(function (texte, k) {
      var o = document.createElement('option');
      o.value = String(k);
      o.textContent = texte;
      select.appendChild(o);
    });
    return select;
  }

  function rendreAssociation(q, ctx) {
    var droites = [];
    q.paires.map(function (p) { return p.droite; }).concat(q.distracteurs || []).forEach(function (d) {
      if (droites.indexOf(d) === -1) droites.push(d);
    });
    droites = melange(droites);

    var groupe = el('fieldset', 'qcm-paires');
    groupe.setAttribute('aria-labelledby', ctx.idEnonce + ' ' + ctx.idConsigne);

    var lignes = melange(q.paires).map(function (p) {
      var ligne = el('div', 'qcm-paire');
      var idSel = uid('paire');
      var label = el('label', 'qcm-paire__gauche', p.gaucheHtml);
      label.htmlFor = idSel;
      var select = creerSelect(droites, idSel);
      var zone = el('div', 'qcm-paire__droite');
      zone.appendChild(select);
      ligne.appendChild(label);
      ligne.appendChild(zone);
      groupe.appendChild(ligne);
      return { p: p, select: select, zone: zone, ligne: ligne };
    });

    return {
      noeud: groupe,
      manque: function () {
        var vide = lignes.filter(function (l) { return l.select.value === ''; })[0];
        if (!vide) return null;
        vide.select.focus();
        return 'Choisissez une réponse pour chaque ligne avant de vérifier.';
      },
      corriger: function () {
        var bons = 0;
        lignes.forEach(function (l) {
          var choisi = droites[Number(l.select.value)];
          var ok = choisi === l.p.droite;
          if (ok) bons += 1;
          // La liste bloquée couperait les réponses longues : on affiche le texte complet à la place.
          var votre = el('p', 'qcm-choisi');
          votre.appendChild(texteEl('span', 'qcm-attendu__titre', 'Votre réponse : '));
          votre.appendChild(document.createTextNode(choisi));
          l.select.disabled = true;
          l.select.hidden = true;
          l.zone.insertBefore(votre, l.select);
          l.ligne.classList.add('qcm-paire--' + (ok ? 'juste' : 'faux'));
          l.zone.appendChild(marque(ok ? 'juste' : 'faux', ok ? 'Juste' : 'Erreur'));
          if (!ok) {
            var bonne = el('p', 'qcm-attendu');
            bonne.appendChild(texteEl('span', 'qcm-attendu__titre', 'Bonne réponse : '));
            bonne.appendChild(document.createTextNode(l.p.droite));
            l.zone.appendChild(bonne);
          }
        });
        var score = lignes.length ? bons / lignes.length : 0;
        return { score: score, etat: etatDe(score, bons === lignes.length), feedbacks: [] };
      }
    };
  }

  function rendreTrous(q, ctx) {
    var trous = q.trous || {};
    var html = String(q.enonceHtml || '').replace(/\{\{(\d+)\}\}/g, function (m, n) {
      return trous[n] ? '<span class="qcm-trou" data-trou="' + n + '"></span>' : m;
    });
    var texte = el('div', 'qcm-texte-trous', html);
    texte.id = ctx.idEnonce;
    var places = Array.prototype.slice.call(texte.querySelectorAll('.qcm-trou'));
    var plusieurs = places.length > 1;

    var champs = places.map(function (place, rang) {
      var n = place.getAttribute('data-trou');
      var t = trous[n];
      var options = t.options || [];
      var etiquette = plusieurs ? 'Trou ' + (rang + 1) : 'Trou';
      var champ = { n: n, t: t, place: place, etiquette: etiquette };

      if (t.mode === 'texte') {
        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'qcm-saisie';
        input.setAttribute('aria-label', etiquette);
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('autocapitalize', 'off');
        input.setAttribute('spellcheck', 'false');
        var longueur = options.reduce(function (m, o) { return Math.max(m, String(o.texte || '').length); }, 6);
        input.size = Math.min(Math.max(longueur + 2, 8), 24);
        place.appendChild(input);
        champ.valeur = function () { return input.value.trim(); };
        champ.focus = function () { input.focus(); };
        champ.bloquer = function () { input.readOnly = true; input.setAttribute('aria-readonly', 'true'); };
        champ.fractionChoisie = function () {
          var trouvee = options.filter(function (o) { return correspond(input.value, o.texte); })[0];
          champ.choisie = trouvee || null;
          return trouvee ? fraction(trouvee.fraction) : 0;
        };
      } else if (t.mode === 'boutons') {
        var ordre = melange(options);
        var groupe = el('span', 'qcm-trou-boutons');
        groupe.setAttribute('role', 'radiogroup');
        groupe.setAttribute('aria-label', etiquette);
        var nom = uid('trou');
        var radios = ordre.map(function (o) {
          var lab = el('label', 'qcm-bouton');
          var r = document.createElement('input');
          r.type = 'radio';
          r.name = nom;
          r.className = 'qcm-option__case';
          lab.appendChild(r);
          lab.appendChild(texteEl('span', null, o.texte));
          groupe.appendChild(lab);
          return { o: o, r: r, lab: lab };
        });
        groupe.addEventListener('change', function () {
          radios.forEach(function (x) { x.lab.classList.toggle('est-coche', x.r.checked); });
        });
        place.appendChild(groupe);
        var cochee = function () { return radios.filter(function (x) { return x.r.checked; })[0]; };
        champ.valeur = function () { return cochee() ? 'x' : ''; };
        champ.focus = function () { radios[0].r.focus(); };
        champ.bloquer = function () { radios.forEach(function (x) { x.r.disabled = true; }); };
        champ.fractionChoisie = function () {
          var c = cochee();
          champ.choisie = c ? c.o : null;
          return c ? fraction(c.o.fraction) : 0;
        };
      } else {
        var ordreL = melange(options);
        var select = creerSelect(ordreL.map(function (o) { return o.texte; }), null, etiquette);
        place.appendChild(select);
        champ.valeur = function () { return select.value; };
        champ.focus = function () { select.focus(); };
        champ.bloquer = function () { select.disabled = true; };
        champ.fractionChoisie = function () {
          var o = select.value === '' ? null : ordreL[Number(select.value)];
          champ.choisie = o;
          return o ? fraction(o.fraction) : 0;
        };
      }
      return champ;
    });

    return {
      noeud: texte,
      enonceInclus: true,
      manque: function () {
        var vide = champs.filter(function (c) { return c.valeur() === ''; })[0];
        if (!vide) return null;
        vide.focus();
        return plusieurs ? 'Complétez chaque trou avant de vérifier.' : 'Complétez le trou avant de vérifier.';
      },
      corriger: function () {
        var total = 0;
        var toutJuste = true;
        var feedbacks = [];
        champs.forEach(function (c) {
          var f = borne(c.fractionChoisie());
          total += f;
          var etat = f >= 0.999 ? 'juste' : (f > 0 ? 'partiel' : 'faux');
          if (etat !== 'juste') toutJuste = false;
          c.bloquer();
          c.place.classList.add('qcm-trou--' + etat);
          c.place.appendChild(marque(etat, etat === 'juste' ? 'Juste' : (etat === 'partiel' ? 'En partie' : 'Erreur')));
          if (etat !== 'juste') {
            var meilleure = (c.t.options || []).reduce(function (m, o) {
              return !m || fraction(o.fraction) > fraction(m.fraction) ? o : m;
            }, null);
            if (meilleure) {
              var att = el('span', 'qcm-attendu qcm-attendu--trou');
              att.appendChild(texteEl('span', 'qcm-attendu__titre', 'Bonne réponse : '));
              att.appendChild(document.createTextNode(meilleure.texte));
              c.place.appendChild(att);
            }
          }
          if (c.choisie && c.choisie.feedback) {
            var item = el('p', 'qcm-feedback__item');
            if (plusieurs) item.appendChild(texteEl('strong', null, c.etiquette + ' : '));
            item.appendChild(document.createTextNode(c.choisie.feedback));
            feedbacks.push(item);
          }
        });
        var score = champs.length ? total / champs.length : 0;
        return { score: score, etat: etatDe(score, toutJuste), feedbacks: feedbacks };
      }
    };
  }

  var TYPES = {
    choix: {
      rendre: rendreChoix,
      consigne: function (q) { return q.multiple ? 'Cochez toutes les bonnes réponses.' : 'Choisissez la bonne réponse.'; },
      valide: function (q) { return Array.isArray(q.reponses) && q.reponses.length > 0; }
    },
    association: {
      rendre: rendreAssociation,
      consigne: function () { return 'Pour chaque ligne, choisissez la réponse qui va avec.'; },
      valide: function (q) { return Array.isArray(q.paires) && q.paires.length > 0; }
    },
    trous: {
      rendre: rendreTrous,
      consigne: function () { return 'Complétez le texte.'; },
      valide: function (q) { return q.trous && /\{\{\d+\}\}/.test(q.enonceHtml || ''); }
    }
  };

  /* ---------- Meilleur score (localStorage, facultatif) ---------- */

  function lireRecord(cle) {
    try {
      var v = JSON.parse(window.localStorage.getItem(cle) || 'null');
      return v && typeof v.points === 'number' && typeof v.total === 'number' && v.total > 0 ? v : null;
    } catch (e) { return null; }
  }

  function ecrireRecord(cle, valeur) {
    try { window.localStorage.setItem(cle, JSON.stringify(valeur)); } catch (e) { /* stockage indisponible : tant pis */ }
  }

  /* ---------- Le moteur ---------- */

  function Qcm(racine, donnees) {
    this.racine = racine;
    this.donnees = donnees;
    this.retour = racine.getAttribute('data-retour') || '../../';
    this.cleRecord = 'hg-qcm-meilleur:' + (donnees.id || racine.getAttribute('data-src'));
    this.questions = (donnees.questions || []).filter(function (q) {
      var type = TYPES[q && q.type];
      return !!(type && type.valide(q));
    });
  }

  Qcm.prototype.commencer = function (donnerFocus) {
    var serie = melange(this.questions);
    var tirage = this.donnees.tirage;
    if (Number.isInteger(tirage) && tirage > 0 && tirage < serie.length) serie = serie.slice(0, tirage);
    this.serie = serie;
    this.resultats = [];
    this.index = 0;
    if (!serie.length) {
      this.racine.innerHTML = '';
      this.racine.appendChild(el('p', 'qcm-erreur', 'Ce QCM ne contient pas encore de question.'));
      return;
    }
    this.afficherQuestion(!!donnerFocus);
  };

  Qcm.prototype.afficherQuestion = function (donnerFocus) {
    var self = this;
    var q = this.serie[this.index];
    var type = TYPES[q.type];
    var total = this.serie.length;
    var numero = this.index + 1;

    var racine = this.racine;
    racine.innerHTML = '';

    var entete = el('div', 'qcm-entete');
    var titre = texteEl('h2', 'qcm-progression', 'Question ' + numero + ' sur ' + total);
    titre.tabIndex = -1;
    var barre = el('div', 'qcm-barre');
    barre.setAttribute('aria-hidden', 'true');
    var rempli = el('span', 'qcm-barre__rempli');
    rempli.style.width = (100 * numero / total) + '%';
    barre.appendChild(rempli);
    entete.appendChild(titre);
    entete.appendChild(barre);
    racine.appendChild(entete);

    var form = el('form', 'qcm-carte');
    form.setAttribute('novalidate', '');
    var ctx = { idEnonce: uid('enonce'), idConsigne: uid('consigne') };
    var vue = type.rendre(q, ctx);

    if (!vue.enonceInclus) {
      var enonce = el('div', 'qcm-enonce', q.enonceHtml);
      enonce.id = ctx.idEnonce;
      form.appendChild(enonce);
    }
    var consigne = texteEl('p', 'qcm-consigne', type.consigne(q));
    consigne.id = ctx.idConsigne;
    form.appendChild(consigne);
    if (vue.enonceInclus) {
      var groupe = el('div', 'qcm-groupe-trous');
      groupe.setAttribute('role', 'group');
      groupe.setAttribute('aria-labelledby', ctx.idConsigne);
      groupe.appendChild(vue.noeud);
      form.appendChild(groupe);
    } else {
      form.appendChild(vue.noeud);
    }

    var alerte = el('p', 'qcm-alerte');
    alerte.setAttribute('role', 'status');
    alerte.setAttribute('aria-live', 'polite');
    form.appendChild(alerte);

    var actions = el('div', 'qcm-actions');
    var verifier = texteEl('button', 'qcm-btn qcm-btn--principal', 'Vérifier');
    verifier.type = 'submit';
    actions.appendChild(verifier);
    form.appendChild(actions);

    var corrige = false;
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      if (corrige) return;
      var message = vue.manque();
      if (message) {
        alerte.textContent = '';
        // Léger délai pour que le lecteur d'écran annonce à nouveau le même message.
        window.setTimeout(function () { alerte.textContent = message; }, 30);
        return;
      }
      corrige = true;
      alerte.textContent = '';
      var res = vue.corriger();
      self.resultats.push({ question: q, score: res.score, etat: res.etat, numero: numero });
      self.afficherCorrection(form, actions, q, res);
    });

    racine.appendChild(form);
    if (donnerFocus) titre.focus();
  };

  Qcm.prototype.afficherCorrection = function (form, actions, q, res) {
    var self = this;
    var bloc = el('section', 'qcm-correction qcm-correction--' + res.etat);
    var idVerdict = uid('verdict');
    bloc.setAttribute('aria-labelledby', idVerdict);

    var verdict = el('h3', 'qcm-verdict', icone(res.etat));
    verdict.appendChild(texteEl('span', null, VERDICTS[res.etat]));
    verdict.id = idVerdict;
    verdict.tabIndex = -1;
    bloc.appendChild(verdict);

    if (res.etat !== 'juste') {
      bloc.appendChild(texteEl('p', 'qcm-aide', q.type === 'choix'
        ? 'Les bonnes réponses sont marquées d’une coche ✓ ci-dessus.'
        : 'Les bonnes réponses sont indiquées ci-dessus.'));
    }

    if (res.feedbacks.length || q.feedbackHtml) {
      var fb = el('div', 'qcm-feedback');
      res.feedbacks.forEach(function (n) { fb.appendChild(n); });
      if (q.feedbackHtml) fb.appendChild(el('div', 'qcm-feedback__general', q.feedbackHtml));
      bloc.appendChild(fb);
    }

    form.insertBefore(bloc, actions);

    actions.innerHTML = '';
    var dernier = this.index >= this.serie.length - 1;
    var suite = texteEl('button', 'qcm-btn qcm-btn--principal', dernier ? 'Voir mon score' : 'Question suivante');
    suite.type = 'button';
    suite.addEventListener('click', function () {
      if (dernier) { self.afficherFin(); } else { self.index += 1; self.afficherQuestion(true); }
    });
    actions.appendChild(suite);
    verdict.focus();
  };

  Qcm.prototype.afficherFin = function () {
    var self = this;
    var total = this.serie.length;
    var points = this.resultats.reduce(function (s, r) { return s + r.score; }, 0);
    points = Math.round(points * 10) / 10;
    var ratio = points / total;

    var ancien = lireRecord(this.cleRecord);
    var nouveauRecord = !ancien || ratio > ancien.points / ancien.total + 1e-9;
    if (nouveauRecord) ecrireRecord(this.cleRecord, { points: points, total: total });

    var racine = this.racine;
    racine.innerHTML = '';
    var fin = el('section', 'qcm-fin');
    var titre = texteEl('h2', 'qcm-fin__titre', 'Votre score');
    titre.tabIndex = -1;
    fin.appendChild(titre);

    var score = el('p', 'qcm-score');
    score.appendChild(texteEl('span', 'qcm-score__points', nombre(points)));
    score.appendChild(document.createTextNode(' sur ' + total));
    fin.appendChild(score);

    var message;
    if (ratio >= 0.999) message = 'Bravo, tout est juste !';
    else if (ratio >= 0.7) message = 'Très bien ! Recommencez pour viser le sans-faute.';
    else if (ratio >= 0.4) message = 'C’est un bon début. Relisez la leçon, puis recommencez.';
    else message = 'Relisez la leçon, puis recommencez : vous allez progresser.';
    fin.appendChild(texteEl('p', 'qcm-fin__message', message));

    if (ancien && !nouveauRecord) {
      fin.appendChild(texteEl('p', 'qcm-record', 'Votre meilleur score : ' + nombre(ancien.points) + ' sur ' + ancien.total + '.'));
    } else if (ancien && nouveauRecord) {
      fin.appendChild(texteEl('p', 'qcm-record', 'C’est votre meilleur score sur cet appareil !'));
    }

    var aRevoir = this.resultats.filter(function (r) { return r.etat !== 'juste'; });
    var zone = el('div', 'qcm-revoir');
    if (aRevoir.length) {
      zone.appendChild(texteEl('h3', 'qcm-revoir__titre', 'Questions à revoir'));
      var liste = el('ul', 'qcm-revoir__liste');
      aRevoir.forEach(function (r) {
        var li = el('li', 'qcm-revoir__item qcm-revoir__item--' + r.etat);
        li.appendChild(marque(r.etat, r.etat === 'partiel' ? 'En partie' : 'Erreur'));
        var txt = el('span', 'qcm-revoir__texte');
        txt.appendChild(texteEl('strong', null, 'Question ' + r.numero + ' : '));
        txt.appendChild(document.createTextNode(abrege(texteSeul(r.question.enonceHtml), 140)));
        li.appendChild(txt);
        liste.appendChild(li);
      });
      zone.appendChild(liste);
    } else {
      zone.appendChild(texteEl('p', 'qcm-revoir__vide', 'Aucune question à revoir.'));
    }
    fin.appendChild(zone);

    var actions = el('div', 'qcm-actions');
    var recommencer = texteEl('button', 'qcm-btn qcm-btn--principal', 'Recommencer');
    recommencer.type = 'button';
    recommencer.addEventListener('click', function () { self.commencer(true); });
    var retour = texteEl('a', 'qcm-btn qcm-btn--secondaire', 'Retour au niveau');
    retour.href = this.retour;
    actions.appendChild(recommencer);
    actions.appendChild(retour);
    fin.appendChild(actions);

    racine.appendChild(fin);
    titre.focus();
  };

  /* ---------- Démarrage ---------- */

  function demarrer() {
    var racine = document.getElementById('qcm');
    if (!racine) return;
    var src = racine.getAttribute('data-src') || 'qcm.json';
    racine.classList.add('qcm');
    racine.setAttribute('aria-busy', 'true');
    racine.innerHTML = '<p class="qcm-chargement">Chargement des questions…</p>';

    fetch(src, { credentials: 'same-origin', cache: 'no-cache' })
      .then(function (rep) {
        if (!rep.ok) throw new Error('HTTP ' + rep.status);
        return rep.json();
      })
      .then(function (donnees) {
        racine.removeAttribute('aria-busy');
        new Qcm(racine, donnees).commencer(false);
      })
      .catch(function (err) {
        racine.removeAttribute('aria-busy');
        racine.innerHTML = '<div class="qcm-erreur" role="alert"><p><strong>Les questions n’ont pas pu se charger.</strong></p>' +
          '<p>Vérifiez votre connexion internet, puis rechargez la page.</p></div>';
        if (window.console) console.warn('[qcm] chargement impossible de ' + src + ' :', err);
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer);
  else demarrer();
})();
