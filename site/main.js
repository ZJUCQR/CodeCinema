// SilverGrass project page: nav, scroll reveal, copy buttons, lightbox, hero video
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
