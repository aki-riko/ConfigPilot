.pragma library

var translations = {
    "en": {
        "reasoning_max": "MAX"
    },
    "zh_CN": {
        "reasoning_max": "最高"
    },
    "zh_TW": {
        "reasoning_max": "最高"
    }
}

function tr(key, language) {
    var dictionary = translations[language] || translations.en
    return dictionary[key] || translations.en[key] || key
}
