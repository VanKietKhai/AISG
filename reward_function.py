class RewardFunction:
    def __init__(self):
        # Trọng số cân bằng (Curriculum Learning)
        # Giai đoạn đầu: Ưu tiên kỹ năng sinh tồn cá nhân
        self.alpha = 0.8  # Trọng số điểm cá nhân
        self.beta = 0.2   # Trọng số điểm đồng đội

        # ==========================================
        # A. ĐIỂM CÁ NHÂN (Individual Rewards)
        # ==========================================
        self.r_damage = 0.01      # Sát thương gây ra (mỗi 1 HP)
        self.r_kill = 1.0         # Hạ gục
        self.r_assist = 0.5       # Hỗ trợ
        self.r_death = -1.0       # Bị hạ gục
        self.r_friendly_fire = -1.5 # Phạt cực nặng lỗi bắn nhầm đồng đội
        self.r_step_penalty = -0.005 # Phạt thời gian để chống hành vi "cắm trại"

        # ==========================================
        # B. ĐIỂM ĐỒNG ĐỘI (Team Rewards)
        # ==========================================
        self.r_round_win = 5.0    # Thắng vòng đấu (Mục tiêu tối thượng)
        self.r_round_loss = -5.0  # Thua vòng đấu
        self.r_plant = 2.0        # Đặt bom thành công
        self.r_defuse = 3.0       # Gỡ bom thành công
        self.r_trade_kill = 1.0   # Hạ kẻ địch vừa giết đồng đội trong vòng 3 giây

    def calculate_reward(self, agent_stats, team_stats, is_late_stage=False):
        """
        Tính toán tổng điểm thưởng cho một Agent ở mỗi step hoặc cuối round.
        
        Args:
            agent_stats (dict): VD: {'damage': 120, 'kills': 1, 'deaths': 0, 'steps': 10}
            team_stats (dict): VD: {'round_win': True, 'defuse': True}
            is_late_stage (bool): Chuyển trọng số khi huấn luyện MAPPO ở giai đoạn sau.
        """
        
        # Chuyển trọng số: Ép bot phối hợp nhóm ở giai đoạn sau của quá trình huấn luyện
        if is_late_stage:
            self.alpha = 0.3
            self.beta = 0.7

        # 1. Tính toán Điểm Cá Nhân
        ind_reward = 0.0
        ind_reward += agent_stats.get('damage', 0) * self.r_damage
        ind_reward += agent_stats.get('kills', 0) * self.r_kill
        ind_reward += agent_stats.get('assists', 0) * self.r_assist
        ind_reward += agent_stats.get('deaths', 0) * self.r_death
        ind_reward += agent_stats.get('friendly_fire', 0) * self.r_friendly_fire
        ind_reward += agent_stats.get('steps', 0) * self.r_step_penalty

        # 2. Tính toán Điểm Đồng Đội
        team_reward = 0.0
        if team_stats.get('round_win', False):
            team_reward += self.r_round_win
        elif team_stats.get('round_loss', False):
            team_reward += self.r_round_loss
            
        if team_stats.get('plant', False):
            team_reward += self.r_plant
        if team_stats.get('defuse', False):
            team_reward += self.r_defuse
        if team_stats.get('trade_kill', False):
            team_reward += self.r_trade_kill

        # 3. Tính Tổng Điểm dựa trên trọng số Curriculum
        total_reward = (self.alpha * ind_reward) + (self.beta * team_reward)
        return total_reward
