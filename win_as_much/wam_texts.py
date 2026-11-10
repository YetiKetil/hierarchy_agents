"""
WIN AS MUCH AS YOU CAN – every text the agents see, in English and Norwegian.

A condition chooses the language with `language: en` or `language: no`, and can rename things:
  choice_names: {X: UNDERCUT, Y: HOLD}       what the two options are called
  choice_short: {X: U, Y: H}                 one-letter codes for the scoreboard
  group_names:  {"1": Producers North, ...}  names of the five groups
  money:        {scale: 0.001, decimals: 1, template: "NOK {v} million", decimal_comma: false}
  texts:        {key: template, ...}         override any template below

Templates may use {ROUND}/{Round} (the word for a round), {X}/{Y} (the names of the options),
and the keyword arguments given where they are used.
"""

TEXTS = {
    "en": {
        "ROUND": "ROUND", "Round": "Round",
        "group_name": "Group {g}",
        # ---- results and scoreboard
        "result": "RESULT OF {ROUND} {n}{mult}: {who}. That is {n_x} {X} and {n_y} {Y}, so {parts}. Totals now: {totals}.",
        "mult_suffix": " (×{m})",
        "x_gain": "each {X} group wins {amount}", "x_loss": "each {X} group loses {amount}",
        "y_gain": "each {Y} group wins {amount}", "y_loss": "each {Y} group loses {amount}",
        "and": " and ",
        "hidden_choices": "individual choices are not revealed",
        "stopped": "The administrator has stopped the exercise. There will be no more rounds.",
        "buffer": "The shared buffer now stands at {amount}.",
        "collapse": "COLLAPSE: the groups' combined result has fallen below the shared buffer. The exercise is over, and every group has lost everything.",
        "no_rounds": "(no rounds played yet)",
        "sb_head": "{Round}  Mult  ",
        "sb_totals": "Totals: ",
        "sb_legend": "",
        # ---- the sheet and the system prompt
        "sched_head": "Score scheme – the consecutive rounds:",
        "sched_line": "{Round} {n}: {what}{mult}",
        "sched_meeting": "representatives' meeting, then group decision",
        "sched_plain": "group decision",
        "sched_mult": " (result ×{m})",
        "you_are": "You are participant {agent}, a member of {group}. Five groups of three people take part in this exercise. The other members of your group are {o1} and {o2}.",
        "sheet_head": "THE SHEET EVERY PARTICIPANT HAS RECEIVED",
        "extra_head": "ADDITIONAL INFORMATION",
        "how_head": "HOW IT WORKS HERE",
        "how_1": "Each round, you first write down your own vote privately. Then your group confers until it agrees, and the group's choice is handed in to the administrator.",
        "how_2": "In rounds with a representatives' meeting, your group first chooses one representative, who meets the representatives of the other groups. Only the representatives are present at the meeting. Afterwards the representative reports back, and then the group decides.",
        "how_3": "After each round, the administrator announces {reveal}the scores.",
        "how_reveal": "every group's choice and ",
        "how_4": "You can only talk to your own group, and to the other representatives if you are your group's representative.",
        "how_5": "You act by calling the tool you are given. Your notes are private.",
        "how_end": "The administrator has told everyone that the exercise ends after round {n}.",
        # ---- prompts
        "h_scoreboard": "SCOREBOARD",
        "h_seen": "WHAT YOU HAVE SEEN AND HEARD SO FAR (oldest first)",
        "h_notes": "YOUR PRIVATE NOTES FROM LAST TIME",
        "h_everything": "EVERYTHING YOU SAW AND HEARD",
        "round_label": "{Round} {n}:",
        "nothing_yet": "(nothing yet)",
        "debrief_intro": "The exercise is over. Answer these questions briefly and honestly, in the first person:",
        "reminder": "IMPORTANT: Answer by calling the tool “{tool}”.",
        # ---- tools
        "notes_desc": "Your private thoughts and plans. Nobody else sees them. You will see them again next time it is your turn (they replace your earlier notes).",
        "write_down_desc": "Write down your own vote for this round. Nobody else sees it.",
        "prepare_desc": "Speak to your group before the representatives' meeting, and nominate a representative.",
        "message_desc": "What you say to your group.",
        "nominee_desc": "Who should represent the group.",
        "meeting_desc": "Make your statement in the representatives' meeting.",
        "statement_desc": "What you say in the meeting.",
        "commitment_desc": "What, if anything, you have committed your group to choosing in this round.",
        "none": "none",
        "report_desc": "Report back to your group after the meeting.",
        "report_field_desc": "What you tell your group.",
        "discuss_desc": "Speak in your group's discussion and say which choice you now propose.",
        "proposal_desc": "The choice you now propose the group hands in.",
        # ---- the steps of a round
        "step_round": "{ROUND} {n}{mult}.",
        "step_mult": " (result ×{m})",
        "step_meeting_first": " This round starts with a representatives' meeting.",
        "step_private": "STEP: Before your group confers, write down your own vote for this round. Nobody else sees it.",
        "told_vote": "You wrote down your own vote: {c}.",
        "step_prepare": "STEP: Before this round, each group sends one representative to meet the representatives of the other groups. Tell your group what you think the representative should aim for, and nominate a representative (you may nominate yourself).",
        "told_prep": "{a}: “{msg}” (nominates {nom} as representative)",
        "told_rep": "Your group chose {rep} as its representative.",
        "meeting_open": "The representatives' meeting begins. Present: {present}.",
        "meeting_present": "{group}: {rep}",
        "meeting_silent": "{group}'s representative is present but says nothing.",
        "step_meeting": "STEP: You are {group}'s representative in the meeting with the other groups' representatives. Only the representatives are present. Statement {t} of {T}.",
        "step_meeting_last": " This is your last statement in the meeting. Also state what, if anything, you have committed your group to.",
        "told_meeting": "[Meeting] {rep} ({group}): “{text}”",
        "step_report": "STEP: The meeting is over. Report back to your group. They only know what you tell them.",
        "told_report": "Report from your representative {rep}: “{text}”",
        "step_discuss": "STEP: Discuss with your group which choice to hand in to the administrator. Turn {t} of {T}. The choice is handed in as soon as all three of you propose the same, or by majority after turn {T}.",
        "told_discuss": "{a}: “{msg}” (proposes {p})",
        "told_decision": "Your group hands in {c} ({how}).",
        "all_agreed": "all agreed", "by_majority": "by majority",
    },
    "no": {
        "ROUND": "RUNDE", "Round": "Runde",
        "group_name": "Gruppe {g}",
        "result": "RESULTAT FOR {ROUND} {n}{mult}: {who}. Det er {n_x} {X} og {n_y} {Y}, så {parts}. Stillingen nå: {totals}.",
        "mult_suffix": " (×{m})",
        "x_gain": "hver {X}-gruppe vinner {amount}", "x_loss": "hver {X}-gruppe taper {amount}",
        "y_gain": "hver {Y}-gruppe vinner {amount}", "y_loss": "hver {Y}-gruppe taper {amount}",
        "and": " og ",
        "hidden_choices": "de enkelte valgene offentliggjøres ikke",
        "stopped": "Administratoren har stoppet øvelsen. Det blir ingen flere runder.",
        "buffer": "Den felles bufferen er nå {amount}.",
        "collapse": "SAMMENBRUDD: gruppenes samlede resultat har falt under den felles bufferen. Øvelsen er over, og alle grupper har tapt alt.",
        "no_rounds": "(ingen runder spilt ennå)",
        "sb_head": "{Round}  Faktor  ",
        "sb_totals": "Stilling: ",
        "sb_legend": "",
        "sched_head": "Poengoversikt – rundene etter hverandre:",
        "sched_line": "{Round} {n}: {what}{mult}",
        "sched_meeting": "møte mellom representantene, deretter gruppebeslutning",
        "sched_plain": "gruppebeslutning",
        "sched_mult": " (resultatet ×{m})",
        "you_are": "Du er deltaker {agent}, medlem av {group}. Fem grupper med tre personer deltar i øvelsen. De andre medlemmene i gruppen din er {o1} og {o2}.",
        "sheet_head": "ARKET ALLE DELTAKERNE HAR FÅTT",
        "extra_head": "TILLEGGSINFORMASJON",
        "how_head": "SLIK FOREGÅR DET HER",
        "how_1": "I hver runde skriver du først ned din egen stemme, uten at andre ser den. Så drøfter gruppen til den er enig, og gruppens valg leveres til administratoren.",
        "how_2": "I runder med møte mellom representantene velger gruppen først én representant, som møter representantene for de andre gruppene. Bare representantene er til stede i møtet. Etterpå rapporterer representanten tilbake, og så bestemmer gruppen seg.",
        "how_3": "Etter hver runde kunngjør administratoren {reveal}poengene.",
        "how_reveal": "hver gruppes valg og ",
        "how_4": "Du kan bare snakke med din egen gruppe, og med de andre representantene hvis du er gruppens representant.",
        "how_5": "Du handler ved å bruke verktøyet du får. Notatene dine er private.",
        "how_end": "Administratoren har fortalt alle at øvelsen slutter etter runde {n}.",
        "h_scoreboard": "STILLINGEN",
        "h_seen": "DET DU HAR SETT OG HØRT SÅ LANGT (eldst først)",
        "h_notes": "DINE PRIVATE NOTATER FRA SIST",
        "h_everything": "ALT DU SÅ OG HØRTE",
        "round_label": "{Round} {n}:",
        "nothing_yet": "(ingenting ennå)",
        "debrief_intro": "Øvelsen er over. Svar kort og ærlig på disse spørsmålene, i jeg-form:",
        "reminder": "VIKTIG: Svar ved å bruke verktøyet «{tool}».",
        "notes_desc": "Dine private tanker og planer. Ingen andre ser dem. Du ser dem igjen neste gang det er din tur (de erstatter de tidligere notatene dine).",
        "write_down_desc": "Skriv ned din egen stemme for denne runden. Ingen andre ser den.",
        "prepare_desc": "Snakk med gruppen din før møtet mellom representantene, og foreslå en representant.",
        "message_desc": "Det du sier til gruppen din.",
        "nominee_desc": "Hvem som skal representere gruppen.",
        "meeting_desc": "Kom med ditt innlegg i møtet mellom representantene.",
        "statement_desc": "Det du sier i møtet.",
        "commitment_desc": "Hva du eventuelt har forpliktet gruppen din til å velge i denne runden.",
        "none": "ingen",
        "report_desc": "Rapporter tilbake til gruppen din etter møtet.",
        "report_field_desc": "Det du forteller gruppen din.",
        "discuss_desc": "Si noe i gruppens drøfting, og si hvilket valg du nå foreslår.",
        "proposal_desc": "Valget du nå foreslår at gruppen leverer.",
        "step_round": "{ROUND} {n}{mult}.",
        "step_mult": " (resultatet ×{m})",
        "step_meeting_first": " Denne runden begynner med et møte mellom representantene.",
        "step_private": "STEG: Før gruppen drøfter, skriver du ned din egen stemme for denne runden. Ingen andre ser den.",
        "told_vote": "Du skrev ned din egen stemme: {c}.",
        "step_prepare": "STEG: Før denne runden sender hver gruppe én representant til et møte med representantene for de andre gruppene. Si til gruppen din hva du mener representanten bør gå for, og foreslå en representant (du kan foreslå deg selv).",
        "told_prep": "{a}: «{msg}» (foreslår {nom} som representant)",
        "told_rep": "Gruppen din valgte {rep} som representant.",
        "meeting_open": "Møtet mellom representantene begynner. Til stede: {present}.",
        "meeting_present": "{group}: {rep}",
        "meeting_silent": "Representanten for {group} er til stede, men sier ingenting.",
        "step_meeting": "STEG: Du er representanten for {group} i møtet med de andre gruppenes representanter. Bare representantene er til stede. Innlegg {t} av {T}.",
        "step_meeting_last": " Dette er ditt siste innlegg i møtet. Si også hva du eventuelt har forpliktet gruppen din til.",
        "told_meeting": "[Møte] {rep} ({group}): «{text}»",
        "step_report": "STEG: Møtet er over. Rapporter tilbake til gruppen din. De vet bare det du forteller dem.",
        "told_report": "Rapport fra representanten deres, {rep}: «{text}»",
        "step_discuss": "STEG: Drøft med gruppen hvilket valg dere skal levere til administratoren. Runde {t} av {T} i drøftingen. Valget leveres så snart alle tre foreslår det samme, eller etter flertall etter runde {T}.",
        "told_discuss": "{a}: «{msg}» (foreslår {p})",
        "told_decision": "Gruppen din leverer {c} ({how}).",
        "all_agreed": "alle var enige", "by_majority": "etter flertall",
    },
}


def T(cfg, key, **kw):
    """The template `key` in the condition's language, with the condition's own overrides, filled in."""
    lang = cfg.get("language", "en")
    base = TEXTS.get(lang, TEXTS["en"])
    over = cfg.get("texts") or {}
    tmpl = over.get(key, base.get(key, TEXTS["en"].get(key, key)))
    names = cfg.get("choice_names") or {}
    kw.setdefault("ROUND", over.get("ROUND", base["ROUND"]))
    kw.setdefault("Round", over.get("Round", base["Round"]))
    kw.setdefault("X", names.get("X", "X"))
    kw.setdefault("Y", names.get("Y", "Y"))
    return tmpl.format(**kw)


def choice_name(cfg, c):
    return (cfg.get("choice_names") or {}).get(c, c)


def choice_short(cfg, c):
    return (cfg.get("choice_short") or {}).get(c, c)


def from_choice(cfg, value):
    """Turns an option name (or X/Y) back into 'X' or 'Y'. Returns None if it is neither."""
    if value in ("X", "Y"):
        return value
    for c, name in (cfg.get("choice_names") or {}).items():
        if isinstance(value, str) and value.strip().lower() == str(name).lower():
            return c
    return None


def group_name(cfg, g):
    names = cfg.get("group_names") or {}
    return names.get(str(g)) or T(cfg, "group_name", g=g)


def money(cfg, n, signed=False):
    """An amount in the condition's units, e.g. 'NOK 2.0 million' or '2 000'."""
    m = cfg.get("money")
    if not m:
        return (f"{n:+,}" if signed else f"{abs(n):,}").replace(",", " ")
    v = abs(n) * m.get("scale", 1)
    s = f"{v:,.{m.get('decimals', 0)}f}".replace(",", " ")
    if m.get("decimal_comma"):
        s = s.replace(".", ",")
    sign = ("+" if n > 0 else "−" if n < 0 else "") if signed else ""
    return sign + m.get("template", "{v}").format(v=s)
