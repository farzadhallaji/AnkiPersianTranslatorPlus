# simple-addon-anki

This Anki add-on enhances your study experience by automatically appending Persian translations to words using Google Translate and Tahlilgaran. It is designed to specifically target the "Persian" field and add translations from Google Translate and the Tahlilgaran dictionary for the "1212 - 3rd Edition TOEFL Vocab for Hardworkers" deck.

The add-on is versatile and can be adapted for any deck you wish to use. To customize the add-on for different decks, simply modify the `deck_name`, `source_field`, and `target_field` parameters accordingly.

```plaintext
Function Signature:
apply_translation_to_deck(deck_name, source_field, target_field)

Example usage in __init__.py on line 271:
apply_translation_to_deck("1212 - 3rd edition TOEFL Vocab for Hardworkers", "Word", "Persian") 
```
