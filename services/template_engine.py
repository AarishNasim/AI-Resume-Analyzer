"""Data-driven resume template catalog used by the gallery and live builder."""

CATEGORIES = {
    'ats': ('ATS-Friendly / Minimalist', 'Clean single-column layouts with standard hierarchy.'),
    'modern': ('Modern / Tech', 'Product-minded layouts for technical and digital roles.'),
    'executive': ('Executive / Corporate', 'Structured leadership layouts with polished detail.'),
    'creative': ('Creative / Design', 'Expressive accents and visual rhythm for makers.'),
    'academic': ('Academic / Research', 'Long-form layouts for publications and project depth.'),
}

FONTS = ['DM Sans', 'Source Sans 3', 'Manrope', 'IBM Plex Sans', 'Libre Baskerville', 'Space Grotesk']
ACCENTS = ['#123c35', '#2457c5', '#b4533c', '#6b4f8a', '#177d78', '#ad6b21', '#35445c', '#2d6a4f', '#9a3f62', '#456990']
LAYOUTS = ['single-column', 'sidebar-left', 'sidebar-right', 'split-header', 'timeline', 'publication']
PATTERNS = ['quiet lines', 'skill rail', 'double rule', 'accent blocks', 'timeline dots', 'research index']
SECTION_SETS = [
    ['summary', 'experience', 'education', 'skills'],
    ['summary', 'skills', 'experience', 'projects', 'education'],
    ['profile', 'experience', 'leadership', 'education', 'skills'],
    ['profile', 'experience', 'projects', 'skills', 'education'],
    ['research', 'education', 'publications', 'projects', 'skills'],
]


def _build_template(index, category_key, category_name, description):
    variant = index % 12 + 1
    layout = LAYOUTS[(index + variant) % len(LAYOUTS)]
    return {
        'id': f'{category_key}-{variant:02d}',
        'name': f'{category_name.split(" /")[0]} {variant:02d}',
        'category': category_key,
        'category_name': category_name,
        'description': description,
        'font': FONTS[index % len(FONTS)],
        'accent': ACCENTS[index % len(ACCENTS)],
        'layout': layout,
        'margins': ['compact', 'balanced', 'airy'][index % 3],
        'pattern': PATTERNS[index % len(PATTERNS)],
        'sections': SECTION_SETS[index % len(SECTION_SETS)],
        'sample': 'Jordan Lee | Product-minded professional',
    }


def all_templates():
    templates = []
    index = 0
    for category_key, (category_name, description) in CATEGORIES.items():
        for _ in range(12):
            templates.append(_build_template(index, category_key, category_name, description))
            index += 1
    return templates


TEMPLATES = all_templates()
TEMPLATE_BY_ID = {template['id']: template for template in TEMPLATES}


def get_template(template_id):
    return TEMPLATE_BY_ID.get(template_id)


def template_choices():
    return {key: {'name': value[0], 'description': value[1]} for key, value in CATEGORIES.items()}
