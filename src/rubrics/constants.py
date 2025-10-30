# src/rubrics/constants.py

SKILL_RUBRICS = {
    "Shooting": {
        "indicators": [
            {
                "title": "Stance & Balance",
                "descriptions": {
                    1: "Player is off-balance; feet are too close or too wide; lands in a different spot than they jumped from; stiff knees.",
                    2: "Stance is sometimes correct, but balance is inconsistent; may fall forward or back after the shot; inconsistent knee bend.",
                    3: "Consistently balanced before, during, and after the shot; feet are shoulder-width apart; demonstrates proper knee flexion for power.",
                },
            },
            {
                "title": "Elbow & Hand Placement",
                "descriptions": {
                    1: "Shooting elbow flares out significantly from the body; ball is held far from the body or on the palm of the hand.",
                    2: "Elbow is sometimes tucked but drifts outward during the shot; hand placement on the ball is inconsistent; guide hand sometimes interferes with the shot.",
                    3: "Shooting elbow is consistently aligned under the ball, creating a straight line to the basket; ball rests on finger pads; guide hand is on the side of the ball for balance only.",
                },
            },
            {
                "title": "Upward Motion & Release",
                "descriptions": {
                    1: 'Shot is a "push" from the chest; motion is jerky or two-part (a pause between jumping and shooting); poor timing; release point is low and inconsistent.',
                    2: "Motion is generally fluid, but there are occasional hitches; release point is inconsistent (sometimes too early, sometimes too late); Energy transfer is inconsistent.",
                    3: "A single, fluid motion from the shot pocket to the release point; energy is transferred smoothly from legs to the ball; consistent release point above the head.",
                },
            },
        ]
    },
    "Dribbling": {
        "indicators": [
            {
                "title": "Control & Hand Position",
                "descriptions": {
                    1: "Dribbles with the palm of the hand (slapping the ball); loses control on simple moves; ball comes up too high (above the waist).",
                    2: "Sometimes uses finger pads but defaults to palm under pressure; control is inconsistent; dribble height varies.",
                    3: 'Consistently uses finger pads for control; keeps the ball low (at or below the waist); the ball appears "on a string."',
                },
            },
            {
                "title": "Stance & Body Position",
                "descriptions": {
                    1: "Dribbles while standing upright, presenting an easy target for defenders; narrow, unstable stance.",
                    2: "Maintains a low stance sometimes but rises up when moving or under pressure; balance is inconsistent; Inconsistent use of the off-arm for protection.",
                    3: "Maintains a low, athletic stance (butt down, back straight) for balance and protection; uses off-arm to shield the ball; well-balanced and protected.",
                },
            },
            {
                "title": "Vision & Awareness",
                "descriptions": {
                    1: "Eyes are focused on the basketball; is unaware of teammates, defenders, or court positioning; watching the ball to maintain control.",
                    2: "Occasionally looks up to scan the court but immediately looks back down at the ball, especially when dribbling with the non-dominant hand; lacks confidence when not looking at the ball.",
                    3: "Keeps head up consistently, scanning the entire court to see teammates and defenders; dribbles confidently without looking at the ball.",
                },
            },
        ]
    },
    "Passing": {
        "indicators": [
            {
                "title": "Mechanics & Technique",
                "descriptions": {
                    1: "Throws from the side or with one hand; no step into the pass; poor hand placement (no follow-through with thumbs down).",
                    2: "Demonstrates correct form (e.g., chest pass, bounce pass) but mechanics break down under pressure or when passing on the move; inconsistent use of a step to generate power; Inconsistent follow-through.",
                    3: "Consistently executes passes with proper technique; steps into the pass for power; crisp wrist snap and follow-through towards the target.",
                },
            },
            {
                "title": "Decision Making & Timing",
                "descriptions": {
                    1: "Passes into heavy traffic, leading to turnovers; telegraphs passes; passes too late, missing the scoring opportunity.",
                    2: "Identifies the correct pass but is often hesitant or late; sometimes forces a pass into a covered teammate; rarely uses fakes.",
                    3: "Reads the defense effectively; delivers the ball on time and on target to an open teammate; uses fakes to create passing lanes.",
                },
            },
            {
                "title": "Velocity & Accuracy",
                "descriptions": {
                    1: "Passes are consistently off-target (too high, too low, behind the receiver); velocity is too weak or too powerful for the receiver to handle.",
                    2: "Accuracy and velocity are acceptable in static drills but become unreliable in game situations or on longer passes; inconsistent velocity control.",
                    3: "Consistently delivers passes that are accurate and easy to catch; adjusts pass velocity appropriately for the situation (e.g., soft touch pass vs. hard skip pass).",
                },
            },
        ]
    },
    "Rebounding": {
        "indicators": [
            {
                "title": "Positioning & Boxing Out",
                "descriptions": {
                    1: "Watches the ball in the air; does not make contact with an opponent; gets pushed under the basket easily.",
                    2: "Attempts to find an opponent to box out but often loses contact or establishes position too late; inconsistent boxing out technique.",
                    3: 'Actively seeks out an opponent as the shot goes up; makes contact ("forearm to back"), gets low, and seals the opponent away from the basket.',
                },
            },
            {
                "title": "Jumping & Timing",
                "descriptions": {
                    1: "Jumps too early or too late for the ball; does not jump aggressively towards the ball's peak.",
                    2: "Times the jump correctly on occasion but is sometimes passive; jumps with one hand instead of two.",
                    3: "Reads the ball's trajectory off the rim; times the jump to meet the ball at the highest point; jumps aggressively with both arms extended.",
                },
            },
            {
                "title": 'Ball Security ("Chinning it")',
                "descriptions": {
                    1: "Brings the ball down to a low position after securing it, making it vulnerable to being stripped; not look for the next play.",
                    2: "Secures the rebound but is inconsistent in protecting it; may allow smaller guards to steal the ball.",
                    3: 'Immediately secures the ball and brings it to "chin level" with elbows out for protection; pivots to look for an outlet pass.',
                },
            },
        ]
    },
    "Defense": {
        "indicators": [
            {
                "title": "Stance & Balance",
                "descriptions": {
                    1: "Stands upright and on flat feet; narrow base; easily knocked off balance by the offensive player.",
                    2: "Starts in a good stance but rises up as soon as the ball-handler moves; balance is easily broken.",
                    3: "Maintains a low, wide, athletic stance consistently; on the balls of their feet, ready to move; balanced and in control.",
                },
            },
            {
                "title": "Footwork & Agility",
                "descriptions": {
                    1: "Crosses feet when sliding, leading to loss of balance; slow to react to changes in direction.",
                    2: "Executes a defensive slide but with choppy steps; sometimes crosses feet when the ball-handler makes a quick move; slow to recover when beaten.",
                    3: "Uses a quick, efficient defensive slide without crossing feet; opens hips to turn and run with the player when beaten.",
                },
            },
            {
                "title": "Positioning & Contesting",
                "descriptions": {
                    1: "Plays too far off the ball-handler or gets too close and is easily driven past; does not contest the shot or contests with the wrong hand.",
                    2: "Maintains good distance sometimes but is vulnerable to jabs or drives; attempts to contest but is often late.",
                    3: "Maintains appropriate spacing to contain the drive while also contesting the shot; forces the ball-handler to their weaker hand; contests shots with a high hand.",
                },
            },
        ]
    },
    "Speed & Agility": {
        "indicators": [
            {
                "title": "Acceleration & First Step",
                "descriptions": {
                    1: "Slow to react; first step is high and lacks power; upright posture when starting a sprint; covers little ground on the first step.",
                    2: "Shows some quickness but first step is inconsistent; takes time to reach top speed; average ground coverage.",
                    3: "Explosive and powerful first step from a low, athletic stance; generates immediate forward momentum; covers ground quickly.",
                },
            },
            {
                "title": "Change of Direction",
                "descriptions": {
                    1: "Rounds out cuts; loses significant speed when changing direction; high center of gravity during cuts.",
                    2: "Can change direction but has to slow down considerably to do so; sometimes loses balance on sharp cuts.",
                    3: "Sinks hips to lower center of gravity before a cut; plants foot and pushes off explosively in the new direction with minimal loss of speed.",
                },
            },
            {
                "title": "Body Control & Deceleration",
                "descriptions": {
                    1: "Has difficulty stopping under control (overruns the spot); lands from jumps with poor balance and stiff legs.",
                    2: "Can stop but requires extra steps; balance is inconsistent when landing, affecting the next move.",
                    3: "Demonstrates excellent body control; can stop on a dime with balance; absorbs force by landing softly with bent knees, ready for the next action.",
                },
            },
        ]
    },
}


def get_rubric(skill_name: str) -> dict | None:
    for key, value in SKILL_RUBRICS.items():
        if key.lower() == skill_name.lower():
            return {"skill_name": key, **value}
    return None


def get_all_skill_names() -> list[str]:
    return list(SKILL_RUBRICS.keys())
