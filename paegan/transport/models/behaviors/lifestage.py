import json
from paegan.transport.models.behaviors.diel import Diel
from paegan.transport.models.behaviors.taxis import Taxis
from paegan.transport.models.behaviors.capability import Capability
from paegan.transport.models.base_model import BaseModel
from paegan.transport.location4d import Location4D
from paegan.utils.asatransport import AsaTransport
import operator

class LifeStage(BaseModel):

    def __init__(self, **kwargs):

        if 'json' in kwargs or 'data' in kwargs:
            data = {}
            try:
                data = json.loads(kwargs['json'])
            except:
                try:
                    data = kwargs.get('data')
                except:
                    pass

            self.name = data.get('name',None)
            self.linear_a = data.get('linear_a', None)
            self.linear_b = data.get('linear_b', None)
            # duration is in days
            self.duration = data.get('duration', None)
            self.diel = [Diel(data=d) for d in data.get('diel')]
            self.taxis = [Taxis(data=t) for t in data.get('taxis')]
            self.capability = None
            if data.get('capability', None) is not None:
                self.capability = Capability(data=data.get('capability'))

    def move(self, particle, u, v, z, modelTimestep, **kwargs):

        particle.temp = kwargs.get('temperature')
        particle.salt = kwargs.get('salinity')

        particle_time = particle.location.time
        # Run the nested behaviors

        # Find the closests Diel that the current particle time is AFTER, and MOVE.
        index, active_diel = min( enumerate(( (d.get_time(loc4d=particle.location) - particle_time).total_seconds() for d in self.diel if d.get_time(loc4d=particle.location) > particle_time )), key=operator.itemgetter(1) )
        diel_results = self.diel[index].move(particle, u, v, self.capability.calculated_vss, modelTimestep, **kwargs)

        # For behaviors, we track the changes in U, V, and Z, not the resulting locations.
        u = diel_results['u']
        v = diel_results['v']
        z = diel_results['z']

        # Analyze past conditions and see if any Taxis should be run
        for t in self.taxis:
            taxis_results = t.move(particle, u, v, self.capability.calculated_vss, modelTimestep, **kwargs)
            u += taxis_results['u']
            v += taxis_results['v']
            z += taxis_results['z']

        # Grow the particle.  Growth affects which lifestage the particle is in.
        do_duration_growth = True
        modelTimestepDays = modelTimestep / 60 / 60 / 24
        if self.linear_a is not None and self.linear_b is not None:
            if particle.temp is not None:
                # linear growth, compute q = t / (Ax+B)
                # Where timestep t (days), at temperature x (deg C), proportion of stage completed (q)
                q = modelTimestepDays / (linear_a * particle.temp + linear_b)
                particle.grow(q)
                do_duration_growth = False
            else:
                print "No temperature found for particle at this location and timestep, skipping linear temperature growth and using duration growth"
                
        if do_duration_growth is True:
            particle.grow(modelTimestepDays / self.duration)

        result = AsaTransport.distance_from_location_using_u_v_z(u=u, v=v, z=z, timestep=modelTimestep, location=particle.location)
        result['u'] = u
        result['v'] = v
        result['z'] = z
        return result
