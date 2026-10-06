// CodeCinema homepage: navigation, inline films, copy buttons and gallery.
(function () {
  var nav = document.querySelector(".nav");
  function onScroll() { nav.classList.toggle("solid", window.scrollY > 40); }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
  }, { rootMargin: "0px 0px -8% 0px" }) : null;
  document.querySelectorAll(".reveal").forEach(function (el) { io ? io.observe(el) : el.classList.add("in"); });

  document.querySelectorAll(".copy").forEach(function (b) {
    b.addEventListener("click", function () {
      var pre = b.closest(".term").querySelector("pre");
      var text = Array.prototype.map.call(pre.querySelectorAll("code"), function (c) { return c.innerText; }).join("\n");
      text = text.split("\n").map(function (l) { return l.replace(/\s+#.*$/, ""); }).join("\n").trim();
      navigator.clipboard.writeText(text).then(function () {
        var t = b.textContent; b.textContent = b.dataset.done || "Copied";
        setTimeout(function () { b.textContent = t; }, 1400);
      });
    });
  });

  var filmVideos = document.querySelectorAll("[data-film] video");
  filmVideos.forEach(function (video) {
    var card = video.closest("[data-film]");
    var versions = Array.from(card.querySelectorAll("[data-film-version]"));
    var download = card.querySelector("[data-film-download]");
    var status = card.querySelector(".player-status");
    var selected = 0;
    var triedFallback = false;

    function selectVersion(index, play) {
      var version = versions[index];
      if (!version) return;
      selected = index;
      video.pause();
      triedFallback = false;
      status.hidden = true;
      versions.forEach(function (button, i) { button.setAttribute("aria-pressed", String(i === index)); });
      video.poster = version.dataset.poster;
      video.setAttribute("aria-label", version.dataset.label);
      video.dataset.fallback = version.dataset.download;
      download.href = version.dataset.download;
      video.src = version.dataset.src;
      video.load();
      if (play) video.play().catch(function () { /* Native controls remain available. */ });
    }

    versions.forEach(function (button, index) {
      button.addEventListener("click", function () {
        if (index !== selected) selectVersion(index, true);
        else video.play().catch(function () {});
      });
    });
    video.addEventListener("ended", function () {
      if (selected > 0 && selected < versions.length - 1) selectVersion(selected + 1, true);
    });
    video.addEventListener("play", function () {
      filmVideos.forEach(function (other) { if (other !== video) other.pause(); });
    });
    function onVideoError() {
      if (!triedFallback && video.dataset.fallback) {
        triedFallback = true;
        var wasPlaying = !video.paused;
        video.src = video.dataset.fallback;
        video.load();
        if (wasPlaying) video.play().catch(function () {});
      } else {
        status.textContent = video.dataset.error;
        status.hidden = false;
      }
    }
    video.addEventListener("error", onVideoError);
    video.querySelectorAll("source").forEach(function (source) {
      source.addEventListener("error", function () {
        if (!video.getAttribute("src")) onVideoError();
      });
    });
  });

  var lb = document.querySelector(".lightbox");
  if (lb) {
    var img = lb.querySelector("img"), cap = lb.querySelector("p");
    document.querySelectorAll(".gallery figure").forEach(function (f) {
      f.addEventListener("click", function () {
        var i = f.querySelector("img");
        img.src = i.src; img.alt = i.alt; cap.innerHTML = f.querySelector("figcaption").innerHTML;
        lb.classList.add("open");
      });
    });
    lb.addEventListener("click", function () { lb.classList.remove("open"); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") lb.classList.remove("open"); });
  }

  var bg = document.querySelector(".hero video.bg");
  if (bg && window.matchMedia("(prefers-reduced-motion: reduce)").matches) { bg.removeAttribute("autoplay"); bg.pause(); }
})();
