from __future__ import division
from hotwing_core.profile import Profile
from hotwing_core.panel import Panel
from hotwing_core.coordinate import Coordinate
from hotwing_core.cutting_strategies.base import CuttingStrategyBase


class TrailingEdgeCuttingStrategy(CuttingStrategyBase):
    """
    Trailing edge first cutting strategy
    """
    def cut(self, horizontal_offset, vertical_offset_left = 0, vertical_offset_right = None, vertical_align_profiles = "default"):
        m = self.machine
        dwell_time = 1
        le_offset = 1
        te_offset = 1

        # sheet profile
        profile2 = m.panel.left_rib.profile
        profile1 = m.panel.right_rib.profile

        # Offset profiles for Kerf Value
        profile1 = Profile.offset_around_profiles(
            profile1, m.kerf[0], m.kerf[0])
        profile2 = Profile.offset_around_profiles(
            profile2, m.kerf[1], m.kerf[1])

        profile_max = max(profile1.right_midpoint.x, profile2.right_midpoint.x)

        if vertical_offset_right is None and vertical_align_profiles == "default":
            vertical_offset_right = vertical_offset_left
        
        if vertical_offset_right is None and vertical_align_profiles == "bottom":
            left_profile_bottom = profile1.bottom.bounds[0].y
            right_profile_bottom = profile2.bottom.bounds[0].y
            vertical_offset_right = vertical_offset_left + left_profile_bottom - right_profile_bottom

        profile1.top.coordinates = [Coordinate(profile_max - c.x + horizontal_offset, c.y + vertical_offset_left) for c in reversed(profile1.top.coordinates)]
        profile1.bottom.coordinates = [Coordinate(profile_max - c.x +horizontal_offset, c.y + vertical_offset_left) for c in reversed(profile1.bottom.coordinates)]

        profile2.top.coordinates = [Coordinate(profile_max - c.x + horizontal_offset, c.y + vertical_offset_right) for c in reversed(profile2.top.coordinates)]
        profile2.bottom.coordinates = [Coordinate(profile_max - c.x + horizontal_offset, c.y + vertical_offset_right) for c in reversed(profile2.bottom.coordinates)]

        # Trim the overlap
        # profile1 = Profile.trim_overlap(profile1)
        # profile2 = Profile.trim_overlap(profile2)
        
        # MOVE TO SAFE HEIGHT
        self._move_to_safe_height()

        # calc le offset pos
        pos = m.calculate_move(
                profile1.left_midpoint - Coordinate(le_offset, 0),
                profile2.left_midpoint- Coordinate(le_offset, 0))

        ## MOVE FAST HORIZONTALLY TO SPOT ABOVE LE OFFSET
        m.gc.fast_move( {'x':pos['x'],'u':pos['u']}, ['initial_move'] )

        ## MOVE DOWN TO JUST ABOVE FOAM
        m.gc.fast_move( {'y':m.foam_height*1.1,'v':m.foam_height*1.1}, ["do_not_normalize", 'initial_move'] )

        # CUT DOWN TO LEADING EDGE OFFSET
        m.gc.move(pos, ['initial_move'])
        self.machine.gc.dwell(dwell_time)

        # CUT INWARDS TO LEADING EDGE
        m.gc.move(m.calculate_move(profile1.left_midpoint, profile2.left_midpoint), ['initial_move'])
        self.machine.gc.dwell(dwell_time)

        # CUT THE TOP PROFILE
        self._cut_top_profile(profile1, profile2, dwell_time, ['profile'])

        # CUT TO TRAILING EDGE AT MIDDLE OF PROFILE
        m.gc.move(
            m.calculate_move(
                profile1.right_midpoint,
                profile2.right_midpoint)
        , ['profile'])
        self.machine.gc.dwell(dwell_time)

        # CUT TO TRAILING EDGE OFFSET
        m.gc.move(
            m.calculate_move(
                profile1.right_midpoint + Coordinate(te_offset,0),
                profile2.right_midpoint + Coordinate(te_offset,0)),
                ['profile']
        )
        self.machine.gc.dwell(dwell_time)

        # CUT TO TRAILING EDGE AT MIDDLE OF PROFILE
        m.gc.move(
            m.calculate_move(
                profile1.right_midpoint,
                profile2.right_midpoint),
            ['profile']
        )

        # CUT BOTTOM PROFILE
        self._cut_bottom_profile(profile1, profile2, dwell_time, ['profile'])

        # CUT TO LEADING EDGE
        m.gc.move(m.calculate_move(profile1.left_midpoint, profile2.left_midpoint), ['profile'])

        # CUT TO LEADING EDGE OFFSET
        m.gc.move(
            m.calculate_move(
                profile1.left_midpoint - Coordinate(le_offset,0),
                profile2.left_midpoint - Coordinate(le_offset,0)), ['profile']
        )
        self.machine.gc.dwell(dwell_time)

        # CUT UPWARD TO JUST ABOVE FOAM
        m.gc.move( {'y':m.foam_height*1.1,'v':m.foam_height*1.1}, ["do_not_normalize","done_profile"] )
        self.machine.gc.dwell(dwell_time*2)

        # MOVE TO SAFE HEIGHT
        m.gc.fast_move( {'y':m.safe_height,'v':m.safe_height}, ["do_not_normalize", "done_profile"] )


        if m.panel.left_rib.front_stock:
            # calculate position above front stock
            r1_stock = m.panel.left_rib.front_stock
            r2_stock = m.panel.right_rib.front_stock
            
            ts_pos = m.calculate_move(
                Coordinate(profile1.right_midpoint.x - r1_stock + m.kerf[0],0),
                Coordinate(profile2.right_midpoint.x - r2_stock + m.kerf[1],0)
            )

            # MOVE HORIZONTALLY TO ABOVE FRONT STOCK
            m.gc.fast_move({'x':ts_pos['x'],'u':ts_pos['u']},["front_stock"] )

            # MOVE DOWN TO JUST ABOVE FOAM
            m.gc.fast_move( {'y':m.foam_height*1.1,'v':m.foam_height*1.1}, ["do_not_normalize","front_stock"] )

            # CUT DOWN TO 0 HEIGHT
            m.gc.move( {'y':0,'v':0}, ["do_not_normalize", "front_stock"] )

            # CUT UP TO JUST ABOVE FOAM
            m.gc.move( {'y':m.foam_height*1.1,'v':m.foam_height*1.1}, ["do_not_normalize", "front_stock"] )
            
            # MOVE UP TO SAFE HEIGHT
            m.gc.fast_move( {'y':m.safe_height,'v':m.safe_height}, ["do_not_normalize", "front_stock"] )


        if m.panel.left_rib.tail_stock:
            r1_stock = self.machine.panel.left_rib.tail_stock
            r2_stock = self.machine.panel.right_rib.tail_stock

            fs_pos = m.calculate_move(
                Coordinate(profile1.left_midpoint.x + r1_stock - m.kerf[0],0),
                Coordinate(profile2.left_midpoint.x + r2_stock - m.kerf[1],0)
            )

            # MOVE HORIZONTALLY TO ABOVE TAIL STOCK
            m.gc.fast_move({'x':fs_pos['x'],'u':fs_pos['u']}, ['tail_stock'] )

            # MOVE DOWN TO JUST ABOVE FOAM
            m.gc.fast_move( {'y':m.foam_height*1.1,'v':m.foam_height*1.1}, ["do_not_normalize", "tail_stock"] )

            # CUT DOWN TO 0 HEIGHT
            m.gc.move( {'y':0,'v':0}, ["do_not_normalize", "tail_stock"] )

            # CUT UP TO JUST ABOVE FOAM
            m.gc.move( {'y':m.foam_height*1.1,'v':m.foam_height*1.1}, ["do_not_normalize", "tail_stock"] )

            # MOVE UP TO SAFE HEIGHT
            m.gc.fast_move( {'y':m.safe_height,'v':m.safe_height}, ["do_not_normalize", "tail_stock"] )




    def _cut_top_profile(self, profile1, profile2, dwell_time, options=[]):
        # cut top profile
        c1 = profile1.top.coordinates[0]
        c2 = profile2.top.coordinates[0]

        a_bounds_min, a_bounds_max = profile1.top.bounds
        b_bounds_min, b_bounds_max = profile2.top.bounds
        a_width = a_bounds_max.x - a_bounds_min.x
        b_width = b_bounds_max.x - b_bounds_min.x

        for i in range(self.machine.profile_points):
            if i == 0:
                self.machine.gc.dwell(dwell_time)
            pct = i / self.machine.profile_points
            c1 = profile1.top.interpolate_around_profile_dist_pct(pct)
            c2 = profile2.top.interpolate_around_profile_dist_pct(pct)
            self.machine.gc.move(self.machine.calculate_move(c1, c2), options)
            if i == 0:
                # dwell on first point
                self.machine.gc.dwell(dwell_time)

        # cut to last point
        self.machine.gc.move(self.machine.calculate_move(profile1.top.coordinates[-1],
                                                        profile2.top.coordinates[-1]), options)
        self.machine.gc.dwell(dwell_time)


    def _cut_bottom_profile(self, profile1, profile2, dwell_time, options):
        # cutting profile from right to left
        c1 = profile1.top.coordinates[-1]
        c2 = profile2.top.coordinates[-1]
        # cut bottom profile
        a_bounds_min, a_bounds_max = profile1.bottom.bounds
        b_bounds_min, b_bounds_max = profile2.bottom.bounds
        a_width = a_bounds_max.x - a_bounds_min.x
        b_width = b_bounds_max.x - b_bounds_min.x

        for i in range(self.machine.profile_points, 0 - 1, -1):
            pct = i / self.machine.profile_points
            c1 = profile1.bottom.interpolate_around_profile_dist_pct(pct)
            c2 = profile2.bottom.interpolate_around_profile_dist_pct(pct)
            self.machine.gc.move(self.machine.calculate_move(c1, c2), options)
            if i == self.machine.profile_points:
                # dwell on first point
                self.machine.gc.dwell(dwell_time)

        self.machine.gc.dwell(dwell_time)