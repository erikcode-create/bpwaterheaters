(function () {
	function ready(callback) {
		if (document.readyState === "loading") {
			document.addEventListener("DOMContentLoaded", callback, { once: true });
			return;
		}
		callback();
	}

	function setFaqPanel(item, isOpen) {
		var button = item.querySelector(".faq__btn");
		var panel = item.querySelector(".faq__panel");
		item.classList.toggle("open", isOpen);
		if (button) button.setAttribute("aria-expanded", isOpen ? "true" : "false");
		if (panel) panel.style.maxHeight = isOpen ? panel.scrollHeight + "px" : "0px";
	}

	function initMap() {
		var el = document.getElementById("bpwh-service-map");
		if (!el || !window.L || el.dataset.ready) return;
		el.dataset.ready = "true";

		var L = window.L;
		var map = L.map(el, {
			center: [39.3, -119.75],
			zoom: 9,
			zoomControl: true,
			scrollWheelZoom: false,
			attributionControl: false,
		});
		L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
			maxZoom: 19,
			subdomains: "abcd",
		}).addTo(map);

		var pins = [
			{ lat: 39.5296, lng: -119.8138, name: "Reno", primary: true },
			{ lat: 39.5349, lng: -119.7527, name: "Sparks" },
			{ lat: 39.1638, lng: -119.7674, name: "Carson City" },
			{ lat: 39.236, lng: -119.5926, name: "Dayton" },
			{ lat: 39.2519, lng: -119.9762, name: "Incline Village" },
			{ lat: 38.9543, lng: -119.7654, name: "Minden" },
			{ lat: 39.608, lng: -119.252, name: "Fernley" },
			{ lat: 38.9399, lng: -119.9772, name: "S. Lake Tahoe" },
			{ lat: 39.328, lng: -120.1833, name: "Truckee" },
		];

		pins.forEach(function (pin) {
			var icon = L.divIcon({
				className: "",
				html:
					'<div class="bp-pin ' +
					(pin.primary ? "primary" : "") +
					'"><span class="lbl">' +
					pin.name +
					'</span><span class="stem"></span><span class="dot"></span></div>',
				iconSize: [80, 50],
				iconAnchor: [40, 50],
			});
			L.marker([pin.lat, pin.lng], { icon: icon, interactive: false, keyboard: false }).addTo(map);
		});

		map.fitBounds(
			L.latLngBounds(
				pins.map(function (pin) {
					return [pin.lat, pin.lng];
				})
			),
			{ padding: [40, 40] }
		);
	}

	ready(function () {
		var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
		var nav = document.querySelector("[data-bpwh-public-nav]");
		if (nav) {
			var updateNav = function () {
				nav.classList.toggle("nav--scrolled", window.scrollY > 8);
			};
			updateNav();
			window.addEventListener("scroll", updateNav, { passive: true });
		}

		var revealItems = Array.prototype.slice.call(document.querySelectorAll(".reveal"));
		if (revealItems.length) {
			if (reduced || !("IntersectionObserver" in window)) {
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
			Array.prototype.forEach.call(list.querySelectorAll(".faq__item"), function (item) {
				setFaqPanel(item, item.classList.contains("open"));
			});
			list.addEventListener("click", function (event) {
				var button = event.target.closest(".faq__btn");
				if (!button || !list.contains(button)) return;
				var item = button.closest(".faq__item");
				var willOpen = !item.classList.contains("open");
				Array.prototype.forEach.call(list.querySelectorAll(".faq__item"), function (section) {
					setFaqPanel(section, false);
				});
				if (willOpen) setFaqPanel(item, true);
			});
		});

		initMap();
	});
})();
