(function () {
	function ready(callback) {
		if (document.readyState === "loading") {
			document.addEventListener("DOMContentLoaded", callback, { once: true });
			return;
		}
		callback();
	}

	ready(function () {
		var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		var nav = document.querySelector("[data-bpwh-public-nav]");

		if (nav) {
			var updateNav = function () {
				nav.classList.toggle("is-scrolled", window.scrollY > 8);
			};
			updateNav();
			window.addEventListener("scroll", updateNav, { passive: true });
		}

		var revealItems = Array.prototype.slice.call(document.querySelectorAll(".bpwh-reveal"));
		if (revealItems.length) {
			if (reducedMotion || !("IntersectionObserver" in window)) {
				revealItems.forEach(function (item) {
					item.classList.add("is-visible");
				});
			} else {
				var observer = new IntersectionObserver(
					function (entries) {
						entries.forEach(function (entry) {
							if (!entry.isIntersecting) return;
							entry.target.classList.add("is-visible");
							observer.unobserve(entry.target);
						});
					},
					{ rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
				);
				revealItems.forEach(function (item) {
					observer.observe(item);
				});
			}
		}

		document.querySelectorAll("[data-bpwh-faq-list]").forEach(function (list) {
			list.addEventListener("click", function (event) {
				var button = event.target.closest(".bpwh-faq__button");
				if (!button || !list.contains(button)) return;
				var item = button.closest(".bpwh-faq__item");
				var isOpen = item.classList.contains("is-open");
				Array.prototype.forEach.call(list.querySelectorAll(".bpwh-faq__item"), function (section) {
					section.classList.remove("is-open");
					var sectionButton = section.querySelector(".bpwh-faq__button");
					if (sectionButton) sectionButton.setAttribute("aria-expanded", "false");
				});
				if (!isOpen) {
					item.classList.add("is-open");
					button.setAttribute("aria-expanded", "true");
				}
			});
		});
	});
})();
