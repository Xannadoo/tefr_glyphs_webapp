from __future__ import annotations

import base64
import csv
from pathlib import Path
from typing import cast

import streamlit as st


CSV_PATH = Path(__file__).with_name("spells_processed.csv")
IMG_DIR = Path(__file__).with_name("img")
GLYPH_COLUMNS = ["G1", "G2", "G3", "G4", "G5", "G6"]
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".bmp"]
MAX_GLYPH_DISPLAY_PX = 57
# Spells above this glyph count are hidden from players by default.
# Enter the GM password in the sidebar to unlock the full spell list.
PLAYER_MAX_GLYPHS = 2
LINKED_GLYPH_GROUPS = [
	{"Evu", "Sen"},
	{"Tira", "Ekat", "Worav"},
]
GLYPH_GROUPS = [
	("Action", ["Evu", "Sen", "Lerru", "Cya", "Chom", "Shass", "Eyama", "Tira", "Ekat", "Worav"]),
	("Attributes", ["Xama", "Gis", "Eja", "Hust"]),
	("Elements", ["Gonde", "Lucha", "Ynn", "Woh", "Voln", "Raghe", "Mu", "Sarr"]),
	("Natural", ["Abon", "Ovet", "Nanu", "Ghe", "Teshet", "Casan"]),
	("Mystical", ["Ghan", "Maef", "Ix", "Ylg", "Ked"]),
]


def _normalize_glyph(value: object) -> str:
	if value is None or value != value:
		return ""
	return str(value).strip()


def _extract_glyphs_from_row(row: dict[str, str]) -> list[str]:
	return [_normalize_glyph(row.get(col, "")) for col in GLYPH_COLUMNS if _normalize_glyph(row.get(col, ""))]


SpellRecord = dict[str, object]


def _spell_glyph_list(spell: SpellRecord) -> list[str]:
	return cast(list[str], spell["glyph_list"])


def _spell_glyph_count(spell: SpellRecord) -> int:
	return int(cast(str, spell["glyph_count"]))


def _linked_glyph_group(glyph: str) -> set[str]:
	for group in LINKED_GLYPH_GROUPS:
		if glyph in group:
			return set(group)
	return {glyph}


def _normalize_selected_glyphs(glyphs: list[str]) -> list[str]:
	selected = set(glyphs)
	for group in LINKED_GLYPH_GROUPS:
		if selected & group:
			selected.update(group)
	return sorted(selected)


def _load_csv_records(csv_path: Path) -> list[SpellRecord]:
	if not csv_path.exists():
		raise FileNotFoundError(
			f"Missing prepared CSV: {csv_path.name}. Run the offline preparation script first."
		)

	records: list[SpellRecord] = []
	with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
		reader = csv.DictReader(handle)
		for row in reader:
			record: SpellRecord = {}
			for key, value in row.items():
				record[key] = value

			glyph_list = [glyph for glyph in str(record.get("glyph_list", "")).split("|") if glyph]
			glyph_set = set(glyph_list)
			glyph_count_text = str(record.get("glyph_count", "0")).strip() or "0"
			try:
				glyph_count = int(glyph_count_text)
			except ValueError as error:
				raise ValueError(f"Invalid glyph_count value in prepared CSV: {glyph_count_text}") from error

			record["glyph_list"] = glyph_list
			record["glyph_set"] = glyph_set
			record["glyph_count"] = glyph_count
			records.append(record)

	return records


@st.cache_data
def load_spells(csv_path: str) -> list[SpellRecord]:
	return _load_csv_records(Path(csv_path))


def find_glyph_image(glyph: str) -> Path | None:
	for ext in IMAGE_EXTENSIONS:
		candidate = IMG_DIR / f"{glyph}{ext}"
		if candidate.exists():
			return candidate
	return None


@st.cache_data
def load_glyph_preview_data_uri(image_path: str) -> str:
	image_bytes = Path(image_path).read_bytes()
	encoded = base64.b64encode(image_bytes).decode("ascii")
	suffix = Path(image_path).suffix.lower().lstrip(".")
	mime_type = "jpeg" if suffix in {"jpg", "jpeg"} else suffix or "png"
	return f"data:image/{mime_type};base64,{encoded}"


def render_glyph_tile(glyph: str, image_path: Path | None) -> None:
	if image_path:
		image_uri = load_glyph_preview_data_uri(str(image_path))
		st.markdown(
			f"""
			<div style="width:1.5cm;height:1.5cm;display:flex;align-items:center;justify-content:center;background:#ffffff;border:1px solid #e6e6e6;border-radius:8px;overflow:hidden;margin:0 auto;">
			  <img src="{image_uri}" alt="{glyph}" style="max-width:100%;max-height:100%;object-fit:contain;display:block;" />
			</div>
			""",
			unsafe_allow_html=True,
		)
		return

	st.markdown(
		f"<div style='width:1.5cm;height:1.5cm;display:flex;align-items:center;justify-content:center;"
		"background:#ffffff;border:1px solid #e6e6e6;border-radius:8px;font-weight:600;margin:0 auto;'>"
		f"{glyph}</div>",
		unsafe_allow_html=True,
	)


def toggle_glyph(glyph: str) -> None:
	selected = set(st.session_state.selected_glyphs)
	linked_group = _linked_glyph_group(glyph)
	if selected & linked_group:
		selected.difference_update(linked_group)
	else:
		selected.update(linked_group)
	st.session_state.selected_glyphs = _normalize_selected_glyphs(sorted(selected))


def select_all_glyphs(all_glyphs: list[str]) -> None:
	st.session_state.selected_glyphs = all_glyphs


def clear_glyphs() -> None:
	st.session_state.selected_glyphs = []
	st.session_state.ked_learned = False


def toggle_ked() -> None:
	st.session_state.ked_learned = not st.session_state.ked_learned


def _gm_password() -> str:
	# Set this in .streamlit/secrets.toml locally, or under
	# App settings -> Secrets in Streamlit Community Cloud:
	#   gm_password = "yourpassword"
	return str(st.secrets.get("gm_password", ""))


def render_gm_unlock() -> bool:
	"""Sidebar GM check. Returns True if the full spell list is unlocked."""
	with st.sidebar:
		st.subheader("Game Master access")
		is_gm = st.checkbox("I'm the GM", value=st.session_state.get("is_gm", False))
		if is_gm:
			expected = _gm_password()
			if not expected:
				st.warning("No gm_password set in secrets — access left locked.")
				st.session_state.is_gm = False
			else:
				entered = st.text_input("GM password", type="password")
				st.session_state.is_gm = entered == expected
				if entered and not st.session_state.is_gm:
					st.error("Incorrect password.")
		else:
			st.session_state.is_gm = False

		if st.session_state.is_gm:
			st.success(f"Unlocked — showing all spells.")
		else:
			st.caption(f"Players see spells up to {PLAYER_MAX_GLYPHS} glyphs.")

	return bool(st.session_state.is_gm)


def main() -> None:
	st.set_page_config(page_title="Glyph Spell Finder", layout="wide")
	st.title("Glyph Spell Finder")
	st.caption("Pick known glyphs, then filter by spell glyph count to see castable spells.")

	if not CSV_PATH.exists():
		st.error(
			"Missing spells_processed.csv. Run `node prepare_spells.mjs` once to generate it from spells_with_summary.csv."
		)
		st.stop()

	try:
		spells = load_spells(str(CSV_PATH))
	except Exception as err:
		st.error(str(err))
		st.stop()

	is_gm = render_gm_unlock()

	all_glyphs = sorted({glyph for spell in spells for glyph in _spell_glyph_list(spell)})
	counts = [_spell_glyph_count(spell) for spell in spells]
	min_count = min(counts)
	true_max_count = max(counts)
	max_count = true_max_count if is_gm else min(true_max_count, PLAYER_MAX_GLYPHS)

	if "selected_glyphs" not in st.session_state:
		st.session_state.selected_glyphs = []
	if "ked_learned" not in st.session_state:
		st.session_state.ked_learned = False

	st.session_state.selected_glyphs = _normalize_selected_glyphs(st.session_state.selected_glyphs)

	controls_left, controls_right = st.columns([3, 2])
	with controls_left:
		st.subheader("Known Glyphs")
	with controls_right:
		col_a, col_b = st.columns(2)
		with col_a:
			st.button(
				"Select all",
				on_click=select_all_glyphs,
				args=(all_glyphs,),
				use_container_width=True,
			)
		with col_b:
			st.button("Clear", on_click=clear_glyphs, use_container_width=True)

	selected_set = set(st.session_state.selected_glyphs)
	for category_name, glyphs in GLYPH_GROUPS:
		st.markdown(f"#### {category_name}")
		glyph_columns = st.columns(5)
		for idx, glyph in enumerate(glyphs):
			with glyph_columns[idx % 5]:
				with st.container(border=True):
					image_path = find_glyph_image(glyph)
					render_glyph_tile(glyph, image_path)
					if glyph == "Ked":
						st.button(
							glyph,
							key="glyph_button_Ked",
							on_click=toggle_ked,
							type="primary" if st.session_state.ked_learned else "secondary",
							use_container_width=True,
						)
					else:
						st.button(
							glyph,
							key=f"glyph_button_{glyph}",
							on_click=toggle_glyph,
							args=(glyph,),
							type="primary" if glyph in selected_set else "secondary",
							use_container_width=True,
						)

	st.divider()
	st.subheader("Filters")

	SLIDER_KEY = "spell_size_range"
	default_upper = min(PLAYER_MAX_GLYPHS, max_count)

	if min_count == max_count:
		# Only one possible glyph-count value is available (typically:
		# a locked-out player whose cap equals the smallest spell size).
		# Streamlit's slider errors if min_value == max_value, so just
		# fix the range instead of rendering a slider.
		count_range = (min_count, max_count)
		st.caption(f"Spell size: {min_count} glyphs (only size currently available to you).")
	else:
		if SLIDER_KEY not in st.session_state:
			st.session_state[SLIDER_KEY] = (min_count, default_upper)
		else:
			lo, hi = st.session_state[SLIDER_KEY]
			lo = min(max(lo, min_count), max_count)
			hi = min(max(hi, min_count), max_count)
			if lo > hi:
				lo, hi = hi, lo
			st.session_state[SLIDER_KEY] = (lo, hi)

		count_range = st.slider(
			"Spell size (glyphs per spell)",
			min_value=min_count,
			max_value=max_count,
			key=SLIDER_KEY,
		)
	if not is_gm:
		st.caption(
			f"🔒 Spells above {PLAYER_MAX_GLYPHS} glyphs are hidden. "
			"Ask your GM for access if you need them."
		)
	glyph_filter = st.multiselect(
		"Filter spells by glyphs",
		options=all_glyphs,
		help="Choose one or more glyphs to narrow the spell list.",
	)
	match_mode = st.radio(
		"Glyph filter mode",
		options=["Any selected glyph", "All selected glyphs"],
		horizontal=True,
	)

	selected_set = set(st.session_state.selected_glyphs)
	st.write(f"Selected glyphs: {len(selected_set)}")
	if selected_set:
		st.write(", ".join(sorted(selected_set)))
	if st.session_state.ked_learned:
		st.info("Ked learned: infinity-Key spells can be made permanent.")

	results = [
		spell
		for spell in spells
		if count_range[0] <= _spell_glyph_count(spell) <= count_range[1]
		and set(_spell_glyph_list(spell)).issubset(selected_set)
	]
	if glyph_filter:
		filter_set = set(glyph_filter)
		if match_mode == "All selected glyphs":
			results = [spell for spell in results if filter_set.issubset(set(_spell_glyph_list(spell)))]
		else:
			results = [spell for spell in results if bool(set(_spell_glyph_list(spell)) & filter_set)]

	st.subheader("Castable Spells")
	st.write(f"Matches: {len(results)}")

	card_columns = st.columns(4, gap="small")
	for idx, spell in enumerate(results):
		with card_columns[idx % 4]:
			with st.container(border=True):
				st.markdown(f"**{spell.get('Spell Glyphs', '')}**")
				st.write(str(spell.get("short_description", "")).strip() or "No short description available.")
				st.caption(f"Glyphs: {_spell_glyph_count(spell)}")

				with st.expander("Show spell details"):
					st.write(f"**Key:** {spell.get('Key', '')}")
					st.write(f"**Rounds:** {spell.get('Rounds', '')}")
					st.write(f"**Effect distance:** {spell.get('Effect distance', '')}")
					st.write(f"**Page:** {spell.get('page', '')}")
					if st.session_state.ked_learned and "∞" in str(spell.get("Key", "")):
						st.success("Permanent eligible with Ked")
					st.markdown("**Full description**")
					st.write(str(spell.get("description", "")).strip())


if __name__ == "__main__":
	main()