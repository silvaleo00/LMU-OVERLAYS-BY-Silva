from .advanced import AdvancedOverlay
from .battle import BattleOverlay
from .damage import DamageOverlay
from .blind_spot import BlindSpotOverlay
from .delta import DeltaOverlay
from .digital_flag import DigitalFlagOverlay
from .engine_temps import EngineTempsOverlay
from .flags import FlagsOverlay
from .fuel import FuelOverlay
from .inputs import InputsOverlay
from .lap_counter import LapCounterOverlay
from .pitbox import PitboxOverlay
from .relative import RelativeOverlay
from .standings import StandingsOverlay
from .team_radio import TeamRadioOverlay
from .tower import TowerOverlay
from .track_limits import TrackLimitsOverlay
from .track_map import TrackMapOverlay
from .tyres import TyresOverlay
from .weather import WeatherOverlay
from .wind import WindOverlay

# Ordem do painel: os ligados por defeito primeiro, os extras (desligados) no fim
ALL = [BlindSpotOverlay, DeltaOverlay, FuelOverlay, RelativeOverlay, TowerOverlay, BattleOverlay, FlagsOverlay,
       PitboxOverlay, TeamRadioOverlay, TrackMapOverlay, InputsOverlay, DigitalFlagOverlay, AdvancedOverlay,
       TrackLimitsOverlay, DamageOverlay, WeatherOverlay, LapCounterOverlay, EngineTempsOverlay,
       StandingsOverlay, TyresOverlay, WindOverlay]
BY_KEY = {cls.key: cls for cls in ALL}
