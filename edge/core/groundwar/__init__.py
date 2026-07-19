"""Production ground-operations rules package (DESIGN §4.2, GROUNDWAR_INTEGRATION_PLAN).

Core-level, pure: no I/O, no async, no Textual/Rich/`edge.art` imports. The
standalone `edge.groundwar` play-test app is promoted into this package one work
package at a time (GW-WP02+); glyph/colour rendering stays in `edge.art`, which
layers styling over the gameplay feature names this package emits.
"""
