"""Screenplay-driven cartoon films.

A screenplay (films/<id>/screenplay.json) casts characters from the library,
places them in library sets and lists shots made of timed beats. This package
compiles it into a frame-accurate plan, paints faces, speaks the dialogue,
directs the camera, and finishes the master; `codecinema.cartoon.blender`
builds and renders the pictures inside Blender. Everything outside the
`blender` subpackage is plain Python, so planning, Foley and subtitles never
need Blender.
"""
