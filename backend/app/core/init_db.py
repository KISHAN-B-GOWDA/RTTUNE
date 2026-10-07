from core.database import Base, engine
from models.experiment import Experiment
from models.measurement import Measurement


def initialize_database():
    Base.metadata.create_all(bind=engine)
