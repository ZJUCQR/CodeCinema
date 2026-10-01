"""
character.py - a cat courtier: Breed + costume + posture, drawn at a scroll position with a pose.
"""
import cat
import body
from ink import Xf


class Character:
    def __init__(self, name, breed, costume, posture="stand", scale=1.0, facing=-1):
        self.name, self.breed, self.costume, self.posture = name, breed, costume, posture
        self.scale, self.facing = scale, facing          # facing -1 = left (native), +1 = right (mirrored)

    def draw(self, canvas, x, y, pose=None, hold=None, extra=None):
        """(x, y) = ground contact point on the scroll. hold(canvas) draws a held prop between the body and the near
        arm (local body frame); extra(canvas, anchors) draws after the head."""
        p = dict(cat.POSE0)
        if pose:
            p.update(pose)
        g = body.GROUND[self.posture]
        with Xf(canvas, x, y, 0, self.scale * (1 if self.facing < 0 else -1), self.scale):
            with Xf(canvas, 0, -g):
                anchors = body.draw_body(canvas, self.breed, self.costume, self.posture, p, hold)
                hx, hy = body.HEAD_AT
                with Xf(canvas, hx + p["head_x"] + p.get("body_x", 0.0), hy + p["head_y"] + p["body_y"], p["head_rot"]):
                    body.hat_back(canvas, self.breed, self.costume, p)
                    cat.draw_head(canvas, self.breed, p,
                                  hat=lambda: body.hat_front(canvas, self.breed, self.costume, p))
                if extra is not None:
                    extra(canvas, anchors)
        return anchors
