import random
import fiona
import math
from time import sleep
from logging import getLogger, INFO
import requests
import matplotlib.pyplot as plt
import matplotlib

plt.interactive(False)
matplotlib.get_backend()
import uuid
import json
from shapely.geometry import shape, MultiPolygon, Point, Polygon
import datetime
import multiprocessing as mp
import logging

logging.basicConfig()

logger = getLogger(__name__)

SHP_PATH=("/home/matt/Documents/esri/taxi/layer0_0.shp")

ENDPOINT = 'http://startupsges.bd.esri.com:6180/geoevent/rest/receiver/rest-json-in_wheels'
OFFLINE = False

DEVICES_COUNT = 50  # number of simulated assets
WKTID = 3857  # wktid of shapefile


class Event(object):
    def __init__(self, pos, polygon, request_feed, sleep=1.):
        """
        Event generator
        :param pos: list
        :param polygon: Polygon
        :param json_feed: dict
        :param sleep: number
        """

        self.pos = pos
        self.pol = polygon
        self.request_feed = request_feed
        self.endpoint = ENDPOINT
        self.sleep = sleep
        self.uuid = str(uuid.uuid4())
        self.__heading = 0
        self._heading((0., 360.))
        self.__step = 0.8
        self.__n_step = random.randrange(0, 59)

    def info(self):
        logger.info('Heading: %s' % self.__heading)
        logger.info('step: %s' % self.__step)

    def walk(self):
        """
        Infinite loop 
        :return: 
        """
        while True:
            try:
                self.__n_step += 1
                self._move()
                feed = self._post()
                yield feed

                self._heading((20., 20.))
                sleep(self.sleep)

            except KeyboardInterrupt:
                break

    def get_status(self):
        if 55 < self.__n_step < 60:
            return 1
        if self.__n_step >60:
            self.__n_step = 0
        return 0

    def _post(self):
        """
        Posting request to server
        :return: 
        """

        feed = dict(
            geometry=dict(
                x=self.pos[0],
                y=self.pos[1],
                z=self.request_feed['floor'],
                spatialReference=dict(wkid=self.request_feed['wkt'])
            ),
            device=self.request_feed['device'],
            objectId=self.uuid,
            objectDesc=self.request_feed['objectDescription'],
            lat=self.pos[0],
            lon=self.pos[1],
            status=self.request_feed['status'][self.get_status()],
            accuracy=random.randrange(1., 3.),
            timerecordstamp=datetime.datetime.utcnow().isoformat()
        )

        jso = json.dumps(feed)
        if not OFFLINE:
            requests.post(self.endpoint, jso,
                          headers={'content-type': 'application/json'})

        return feed

    def _move(self):
        """
        Walk almost straight, if go out of polygon turn back
        :return: 
        """
        xn = self.__step * math.cos(self.__heading) + self.pos[0]
        yn = self.__step * math.sin(self.__heading) + self.pos[1]
        if self.in_shape([xn, yn]):
            self.pos = [xn, yn]
        else:
            # if wall turn back
            self._heading((0, 10))
            self._move()

    def _heading(self, lims):
        """
        Calculating heading
        :param lims: 
        :return: 
        """
        self.__heading += math.radians(random.uniform(-lims[0], lims[1]))

    def in_shape(self, pos):
        """
        Polygon policy
        :param pos: shapely object
        :return: 
        """
        return Point(pos).within(self.pol)


def random_points_within(poly, num_points):
    min_x, min_y, max_x, max_y = poly.bounds
    points = []
    while len(points) < num_points:
        x, y = random.uniform(min_x, max_x), random.uniform(min_y, max_y)
        random_point = Point([x, y])
        if random_point.within(poly):
            points.append([x, y])
    return points


def generate_assets(number, floor=1):
    """
    Generator of moving assents
    :param number: 
    :param floor: 
    :return: 
    """
    percent2num = lambda x: max(1., float(number) / 100. * x)

    objects = dict(taxi=percent2num(20.),
                   visitor_taxi=percent2num(20.))

    device = ['android', 'ios']
    status = dict(taxi=['free', 'occupied'],
                  visitor_taxi=['ok', 'free'])

    out = []
    for obj, num in objects.items():
        for item in range(int(num)):
            out.append(dict(
                floor=str(floor),
                device=device[random.randint(0, 1)],
                objectDescription=obj,
                status=status[obj],
                wkt=WKTID)
            )
    return out


def simulate((data, position, polygon)):
    evnt = Event(position, polygon, data)
    if OFFLINE:
        drawer = PltAnimator(polygon=polygon)
    try:
        for feed in evnt.walk():
            logger.info(feed)
            if OFFLINE:
                drawer.set_point(feed['lat'], feed['lon'])
                plt.savefig('/tmp/%s.png' % feed['objectId'])
    except:
        pass

class PltAnimator(object):
    def __init__(self, polygon):
        fig, ax = plt.subplots()
        bounds = polygon.bounds
        ax.set_xlim(bounds[0], bounds[2])
        ax.set_ylim(bounds[1], bounds[3])

        for pol in polygon:
            x, y = pol.exterior.xy
            ax.plot(x, y, color='#6699cc', alpha=0.7,
                    linewidth=3, solid_capstyle='round', zorder=2)
        self.points, = ax.plot(
            (bounds[0] + bounds[2]) / 2,
            (bounds[1] + bounds[3]) / 2,
            marker='o', linestyle='None')

    def set_point(self, x, y):
        self.points.set_data(x, y)


def main():
    logger.setLevel(INFO)
    shp = fiona.open(SHP_PATH)

    bounds = MultiPolygon(
        [shape(pol['geometry']) for pol in shp])
    feed = generate_assets(DEVICES_COUNT)
    poi = random_points_within(bounds, DEVICES_COUNT)

    pool = mp.Pool(DEVICES_COUNT)
    data = [(fd, p, bounds) for fd, p in zip(feed, poi)]
    logger.info('number of observations %s' % len(data))
    pool.map(simulate, data)


if __name__ == '__main__':
    main()
