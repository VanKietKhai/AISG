# Hướng dẫn Tích hợp Cơ chế Súng vào Agent

Phiên bản: 1.0  
Ngày cập nhật: 2026-06-21  
Repository: `https://github.com/VanKietKhai/AISG`

## 1. Mục tiêu

Tính năng này bổ sung ba loại súng `SNIPER`, `AR` và `SMG` vào game server và
kết nối trạng thái súng với agent H-MoE có sẵn.

Sau khi tích hợp:

- mỗi agent được server gán một loại súng;
- mỗi agent có ammo, reload, cooldown và bloom riêng;
- tốc độ di chuyển phụ thuộc mobility của súng;
- damage phụ thuộc loại súng và khoảng cách;
- agent nhận trạng thái súng thật từ server;
- H-MoE thay đổi khoảng cách giao tranh và quyết định bắn theo loại súng;
- server vẫn là nơi quyết định phát bắn, va chạm và damage có hợp lệ hay không.

## 2. Nguyên tắc thiết kế

### Server là nguồn dữ liệu chính

Agent chỉ gửi yêu cầu di chuyển, ngắm và bắn. Agent không được tự sửa:

- ammo;
- trạng thái reload;
- cooldown;
- bloom;
- projectile;
- hit hoặc damage;
- kill/death.

Toàn bộ các giá trị trên được tính và xác nhận trong game server.

### Trạng thái súng tách riêng theo từng bot

Mỗi bot có một `WeaponRuntimeState` riêng. Không dùng chung ammo, reload hoặc
bloom giữa các bot, kể cả khi chúng sử dụng cùng loại súng.

### Config có version

Các chỉ số súng nằm trong `weapon_config.json`. Game state giữ một config
snapshot trong suốt trận để tránh thay đổi luật giữa trận.

### Không ghi đè công việc của người khác

- File mới của tính năng được đặt trong module/thư mục riêng.
- File gốc chỉ được thay đổi tại điểm nối tối thiểu khi chủ sở hữu code review và
  chấp thuận.
- Không thay nguyên file bằng bản local và không giải quyết conflict bằng cách
  chọn toàn bộ “ours” hoặc “theirs”.
- Không trộn refactor, format, security hoặc cleanup không cần thiết vào diff
  weapon.
- Nếu áp dụng quy tắc tuyệt đối “chỉ được thêm file mới”, weapon domain có thể
  được commit nhưng **chưa thể hoạt động trong agent/server cũ** vì repository
  hiện không có plugin hook cho physics, observation và H-MoE.
- Cách tích hợp được đề xuất là: thêm module mới trước, sau đó gửi các patch điểm
  nối nhỏ để chủ sở hữu từng file duyệt. Chưa được duyệt thì không stage patch
  của file gốc.

## 3. Cấu hình ba loại súng

File `weapon_config.json` chứa điểm thiết kế và giá trị reload:

- `damage`: điểm sát thương từ 1 đến 10;
- `fire_rate`: điểm tốc độ bắn từ 1 đến 10;
- `range`: điểm tầm bắn từ 1 đến 10;
- `mobility`: điểm cơ động từ 1 đến 10;
- `bloom_recoil`: điểm bloom/recoil từ 1 đến 10;
- `magazine`: số đạn trong băng;
- `reload_seconds`: thời gian reload.

Validation phía server yêu cầu:

- đủ ba key `SNIPER`, `AR`, `SMG`;
- năm điểm thiết kế là số nguyên trong khoảng 1–10;
- `magazine` là số nguyên trong khoảng 1–100;
- `reload_seconds > 0`;
- tốc độ hồi bloom lớn hơn 0;
- `schema_version` được server hỗ trợ;
- `version` không được rỗng.

Giá trị runtime được tính bằng các công thức:

```text
base_damage       = damage * 5
shots_per_second  = 0.5 + 0.75 * fire_rate
shot_cooldown     = 1 / shots_per_second
max_range         = range * 60
speed_multiplier  = 0.70 + 0.06 * mobility
bloom_per_shot    = 0.20 + 0.18 * bloom_recoil
```

Damage giảm theo khoảng cách:

```text
ratio  = distance / max_range
damage = base_damage * (1 - ratio²)
```

Khi `distance >= max_range`, damage bằng 0 và projectile hết hiệu lực.

### Giá trị baseline hiện tại

| Súng | Damage | Phát/giây | Cooldown | Max range | Mobility | Bloom/phát | Băng đạn | Reload |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sniper | 50 | 1.25 | 0.800s | 600px | 0.88x | 2.00° | 5 | 2.5s |
| AR | 20 | 5.75 | 0.174s | 420px | 1.00x | 1.64° | 30 | 2.0s |
| SMG | 15 | 8.00 | 0.125s | 120px | 1.24x | 0.74° | 30 | 1.6s |

Các giá trị trong bảng là kết quả tính từ `weapon_config.json`, không phải một
bản config thứ hai. Khi config thay đổi, tài liệu/report cần ghi rõ version đã
được sử dụng.

### Phân biệt cơ chế đã có và thuật ngữ thống kê

- Mỗi fire action hợp lệ hiện tạo **một projectile**. Chưa có burst-fire mode
  tạo nhiều projectile trong một action.
- `avg_burst_size` trong evaluator là cách nhóm nhiều phát bắn gần nhau theo
  tick; đây là metric hành vi, không phải một cơ chế burst riêng của server.
- `bloom_recoil` hiện điều khiển độ lệch góc projectile. Chưa có camera kick hoặc
  aim kick riêng; vì vậy nên gọi chính xác là bloom/spread khi mô tả gameplay.
- Reload hiện tự động khi ammo bằng 0. Chưa có manual reload action.

## 4. Luồng hoạt động sau khi tích hợp

```text
Admin/UI tạo config draft
        |
        v
weapon_config.json có version
        |
        v
GameEngine load WeaponConfigSnapshot
        |
        v
RoomManager gán SNIPER / AR / SMG cho agent
        |
        v
GameState tạo WeaponRuntimeState riêng cho từng bot
        |
        v
PhysicsEngine xử lý ammo / reload / cooldown / bloom / mobility
        |
        +------------------> projectile / collision / falloff / damage
        |                                      |
        v                                      v
GameState tạo weapon observation         weapon event phía server
        |                                      |
        v                                      v
gRPC Observation                         JSON telemetry
        |                                      |
        v                                      v
BotClient chuyển đổi dữ liệu             Weapon evaluator
        |
        v
H-MoE chọn expert và chiến thuật theo súng
        |
        v
BotClient gửi move / aim / fire action
        |
        v
Server kiểm tra lại action và cập nhật game state
```

Điểm quan trọng:

- UI chỉ tạo hoặc hiển thị config, không quyết định kết quả combat.
- Agent chỉ quyết định chiến thuật, không tự sửa trạng thái súng.
- PhysicsEngine là nơi duy nhất tạo projectile và áp damage.
- Telemetry lấy từ event phía server, không tin hoàn toàn dự đoán client.
- Một config snapshot không thay đổi trong lúc trận đang chạy.

## 5. Cách server áp dụng cơ chế súng

### Khởi tạo bot

Khi bot vào room:

1. `RoomManager` chọn loại súng theo `weapon_loadout_cycle` của room.
2. `GameState` lấy `WeaponDefinition` tương ứng.
3. Server tạo một `WeaponRuntimeState` mới cho bot.
4. Ammo ban đầu bằng kích thước magazine.

### Bắn

Server chỉ tạo projectile khi:

- bot còn sống;
- ammo lớn hơn 0;
- cooldown đã về 0;
- bot không reload.

Khi phát bắn hợp lệ:

1. server lấy bloom hiện tại;
2. tạo sai lệch góc đạn bằng random generator theo match seed;
3. tạo projectile;
4. trừ một ammo;
5. đặt cooldown mới;
6. tăng bloom.

### Reload

Khi ammo về 0, weapon state tự bắt đầu reload. Timer reload sử dụng simulation
time. Khi timer về 0, ammo được phục hồi về kích thước magazine.

### Bloom và recoil

Mỗi phát bắn làm tăng bloom. Bloom giảm dần theo thời gian. Projectile angle
được tạo từ aim angle cộng với sai lệch nằm trong bloom hiện tại.

### Mobility

Acceleration và maximum speed của bot được nhân với `speed_multiplier` của
loại súng. Vì vậy SMG cơ động hơn AR và Sniper.

### Range, falloff và va chạm

Projectile theo dõi tổng quãng đường đã đi. Damage được tính tại vị trí va chạm
thật. Swept collision kiểm tra cả đoạn di chuyển giữa hai tick để tránh đạn tốc
độ cao xuyên qua bot hoặc vật cản.

Đoạn projectile cuối cùng vẫn được kiểm tra va chạm trước khi bị xóa do hết tầm
bắn.

### Respawn

Khi bot respawn:

- ammo trở về đầy băng;
- cooldown bằng 0;
- reload bị hủy;
- bloom bằng 0.

## 6. Contract giữa server và agent

`proto/arena.proto` bổ sung các trường weapon trong Observation:

- `weapon_type`;
- `ammo`;
- `magazine_size`;
- `is_reloading`;
- `reload_progress`;
- `reload_time_remaining`;
- `shot_cooldown_remaining`;
- `current_bloom`;
- `weapon_config_version`;
- `weapon_base_damage`;
- `weapon_max_range`;
- `weapon_shots_per_second`;
- `weapon_mobility_multiplier`;
- `target_distance`;
- `in_effective_range`;
- `can_shoot`.
- `last_shot_elapsed`;
- `self_kills` và `self_deaths`;
- `run_mode`.

`target_distance`, LOS và effective range được tính cho enemy còn sống gần nhất
mà server chọn làm target observation. Trong trận có nhiều đối thủ, agent hiện
không nhận danh sách đầy đủ trạng thái súng/HP của mọi enemy.

RegistrationResponse trả thêm `weapon_type` và `weapon_config_version` để client
biết loadout ngay sau khi đăng ký.

Các field protobuf được thêm mới, không tái sử dụng field number cũ. Khi sửa
`arena.proto`, phải sinh lại đồng thời:

- `proto/arena_pb2.py`;
- `proto/arena_pb2_grpc.py`.

`arena_pb2_grpc.py` phải giữ import tương đối:

```python
from . import arena_pb2 as arena__pb2
```

## 7. Cách BotClient và H-MoE sử dụng súng

### BotClient

`ai_bot/client/bot_client.py` chuyển Observation protobuf thành dictionary và
gửi toàn bộ trạng thái súng cho H-MoE.

Trước khi gửi fire action, BotClient kiểm tra:

- H-MoE có yêu cầu bắn hay không;
- ammo còn hay không;
- có đang reload không;
- cooldown đã hết chưa;
- server diagnostic `can_shoot`;
- target có trong effective range không;
- có line of sight không;
- góc ngắm có đủ chính xác không.

Chỉ có một action producer theo observation để tránh neutral action ghi đè hoặc
làm loãng quyết định bắn của agent.

### H-MoE

H-MoE vẫn sử dụng các expert navigation, evasion và combat có sẵn. Sau khi expert
chọn action, weapon policy áp dụng ràng buộc cuối cùng.

#### Sniper

- Lùi lại khi đối thủ quá gần.
- Tiến nhẹ nếu đối thủ quá xa.
- Strafe khi đã ở khoảng cách phù hợp.
- Chỉ bắn khi bloom thấp và LOS rõ.

#### AR

- Ưu tiên tầm trung.
- Lùi kết hợp strafe ở cự ly quá gần.
- Tiến lên khi mục tiêu nằm ngoài dải giao tranh phù hợp.
- Sử dụng nhịp bắn có kiểm soát.

#### SMG

- Chủ động áp sát.
- Strafe mạnh khi đã ở cự ly gần.
- Không bắn ngoài effective range.
- Dừng bắn trong lúc reload hoặc cooldown.

## 8. Telemetry và đánh giá hiệu quả

Server có thể ghi các weapon event:

- `shot_fired`;
- `shot_rejected`;
- `hit_registered`;
- `reload_started`;
- `reload_finished`;
- `shot_missed`.

Mỗi event có `tick`, `room_id`, `weapon_config_version` và `match_seed`. Payload
chính cần giữ ổn định:

| Event | Dữ liệu quan trọng |
|---|---|
| `shot_fired` | shooter, weapon, bullet ID, ammo trước/sau, aim/projectile angle, bloom, range, LOS và target distance. |
| `shot_rejected` | shooter, weapon, lý do, ammo, cooldown và reload remaining. |
| `hit_registered` | shooter, target, source weapon, bullet ID, khoảng cách, damage, target HP và validation flags. |
| `reload_started` | bot, weapon, ammo trước reload và thời gian reload dự kiến. |
| `reload_finished` | bot, weapon và ammo trước/sau khi hoàn thành. |
| `shot_missed` | shooter, weapon, bullet ID, quãng đường và lý do wall/boundary/max range. |

Tên event và field là contract của evaluator. Nếu đổi tên phải cập nhật evaluator
và test trong cùng commit.

`ai_bot/evaluation/weapon_evaluator.py` đọc server log đã đóng và tổng hợp:

- số episode hoàn thành;
- khoảng cách giao tranh trung bình;
- mức tuân thủ dải khoảng cách;
- số phát bắn và hit hợp lệ;
- hit rate;
- ammo đã sử dụng;
- hit efficiency;
- số lần reload;
- phát bắn không LOS;
- phát bắn ngoài range;
- kill/death;
- damage được server xác nhận.

File log phải được đóng trước khi đưa vào evaluator để JSON array hoàn chỉnh.

### Giới hạn hiện tại của evaluator

Các metric sau chưa đủ mạnh để dùng làm bằng chứng Gate cuối cùng:

- `episode_count` và `completion_rate` hiện suy ra từ death counter, chưa có
  event `episode_started`/`episode_completed` độc lập.
- `avg_burst_size` đang gom phát bắn bằng khoảng cách cố định 15 tick, chưa dựa
  trên fire cadence của từng loại súng.
- `timely_reload_rate` hiện chủ yếu kiểm tra reload khi ammo còn không quá 1;
  trong khi server đang auto reload ở ammo 0 nên metric này gần như luôn pass.
- `stuck_or_idle_penalty_count` hiện là giá trị dự phòng 0, chưa được tính từ
  server/action telemetry.
- `completion_rate` không được dùng để duyệt Gate cho đến khi lifecycle episode
  được định nghĩa và log rõ ràng.

## 9. Các file thuộc tính năng

### Nhóm bắt buộc để cơ chế súng chạy trên agent có sẵn

Các file trong nhóm này phải được review và đi cùng nhau. Thiếu một lớp có thể
làm server dùng config mới nhưng agent không nhận được state, hoặc agent gửi
quyết định dựa trên dữ liệu không tồn tại.

#### Cơ chế súng phía server

- `weapon_config.json`
- `game_server/weapons/__init__.py`
- `game_server/weapons/models.py`
- `game_server/weapons/registry.py`
- `game_server/engine/game_state.py`
- `game_server/engine/physics.py`
- `game_server/main.py`
- `game_server/networking/room_manager.py`
- `game_server/networking/server.py`
- `rooms.json`

#### Contract và agent

- `proto/arena.proto`
- `proto/arena_pb2.py`
- `proto/arena_pb2_grpc.py`
- `ai_bot/client/bot_client.py`
- `ai_bot/models/hmoe_model.py`

### Nhóm đo lường hiệu quả

Các file này không tạo ra projectile nhưng cần để chứng minh agent thực sự sử
dụng cơ chế súng đúng cách:

- `game_server/logging/json_logger.py`
- `ai_bot/evaluation/__init__.py`
- `ai_bot/evaluation/weapon_evaluator.py`

### Nhóm kiểm thử bắt buộc

- `tests/__init__.py`
- `tests/test_weapon_system.py`

### Nhóm UI và tài liệu cân bằng súng

Nếu UI được duyệt cùng tính năng, repository sẽ có:

- `weapon_balance_module/weapon-balance-panel.js`
- `weapon_balance_module/preview.html`
- `weapon_balance_module/README.md`

UI đọc `weapon_config.json`, hiển thị các giá trị runtime và phát event chứa
config draft. UI không tự lưu hoặc publish config lên server.

## 10. Trạng thái chức năng Admin điều chỉnh súng

### Hiện đã có

- Schema và validation của `weapon_config.json`.
- Config có `schema_version` và `version`.
- UI draft độc lập hiển thị slider, runtime, falloff và biểu đồ so sánh.
- UI có thể đọc config, reset config và phát `weapon-config-change` event.
- Game server có thể khởi động với một file weapon config được chỉ định.

### Hiện chưa có

Chức năng Admin hoàn chỉnh **chưa được triển khai**. Hiện chưa có:

- đăng nhập và phân quyền Admin;
- API đọc/lưu config draft;
- API validate config phía server;
- thao tác publish version mới;
- lịch sử version và audit người chỉnh;
- rollback về version cũ;
- cơ chế thông báo publish thành công/thất bại;
- quy tắc áp config mới cho room hoặc match;
- nguồn schema/runtime conversion dùng chung giữa UI và server.

UI hiện tại chỉ là trình chỉnh draft phía trình duyệt. Không được nối UI trực
tiếp vào file config production hoặc cho phép trình duyệt tự ghi
`weapon_config.json`.

UI hiện lặp lại một số default và công thức runtime bằng JavaScript. Trước khi
coi UI là công cụ Admin production, phải loại nguy cơ công thức UI lệch với
`WeaponDefinition` phía server; kết quả server luôn được ưu tiên.

### Luồng Admin cần triển khai thêm

```text
Admin đăng nhập
      |
      v
UI tải active config và draft gần nhất
      |
      v
Admin chỉnh slider
      |
      v
Admin API validate schema + miền giá trị + đủ SNIPER/AR/SMG
      |
      v
Lưu draft, chưa ảnh hưởng trận đang chạy
      |
      v
Admin chọn Publish
      |
      v
Tạo version mới bất biến + audit record
      |
      v
Room/match mới nhận config snapshot mới
      |
      v
Trận đang chạy tiếp tục dùng snapshot cũ
```

Rollback không được sửa đè version cũ. Rollback phải tạo một version mới có nội
dung lấy từ version được chọn và ghi lại audit.

## 11. Kiểm thử tự động

Chạy test từ repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
python3 -m unittest discover -s tests -v
```

Test của tính năng cần bao phủ:

- config validation và tính bất biến;
- công thức runtime;
- damage falloff;
- deterministic seed và loadout;
- ammo và cooldown;
- reload timing và event sequence;
- bloom có thể tái hiện;
- mobility theo loại súng;
- respawn reset;
- giới hạn range;
- projectile collision;
- protobuf round trip;
- weapon observation;
- H-MoE behavior của Sniper, AR và SMG;
- evaluator sử dụng server-validated event.

Trước khi commit phải chạy thêm:

```bash
git diff --check
PYTHONDONTWRITEBYTECODE=1 python3 game_server/main.py --help
PYTHONDONTWRITEBYTECODE=1 python3 -m ai_bot.main --help
```

## 12. Kế hoạch test trên map cho Gate G5

Automated test chỉ chứng minh từng cơ chế hoạt động đúng. Để chứng minh agent sử
dụng súng hiệu quả, cần chạy batch evaluation trong game thật trên nhiều kiểu
map.

### Ma trận test đề xuất

Mỗi loại súng cần được chạy trên ít nhất ba kiểu bố cục:

1. Map mở, ít vật cản: kiểm tra range, Sniper spacing và long-range accuracy.
2. Map có nhiều cover: kiểm tra LOS, reposition và invalid shot.
3. Map có đường hẹp/cự ly gần: kiểm tra SMG approach, AR retreat và reload.

Sử dụng các room trong `rooms.json` nếu chúng đại diện đủ ba kiểu bố cục. Nếu
chưa đủ, Game Design cần điều chỉnh hoặc bổ sung room fixture trước khi chạy
Gate; không thay map giữa các lần so sánh cùng một seed.

Tại thời điểm viết tài liệu, ba room hiện tại đều có kích thước `2000x1500` và
chỉ có từ một đến hai obstacle. Chúng phù hợp để kiểm tra map mở/light cover,
nhưng chưa đủ bằng chứng cho map hành lang hẹp hoặc cover dày. Cần bổ sung fixture
map test được Game Design duyệt trước khi kết luận hành vi SMG/AR/Sniper trên mọi
kiểu địa hình.

Ma trận tối thiểu cần bao phủ:

```text
SNIPER x mỗi map x mỗi seed x N episode
AR     x mỗi map x mỗi seed x N episode
SMG    x mỗi map x mỗi seed x N episode
```

N và số seed phải do PM/Game Design chốt. Gợi ý khởi đầu để khảo sát là ít nhất
30 episode hoàn thành cho mỗi loại súng trên mỗi nhóm map, nhưng đây chưa phải
ngưỡng Gate được duyệt.

### Điều kiện phải giữ cố định

- cùng `weapon_config_version`;
- cùng map và obstacle cho các súng được so sánh;
- cùng tập seed;
- cùng số lượng agent;
- cân bằng/luân phiên join order vì loadout được gán theo thứ tự vào room;
- cùng tick rate và speed multiplier;
- cùng điều kiện kết thúc episode;
- optimizer bị tắt;
- `run_mode = EVAL`;
- `optimizer_step_count = 0`.

### Quy trình chạy

1. Khởi động server headless và bật JSON logging.
2. Kết nối đủ agent để loadout cycle tạo ra Sniper, AR và SMG.
3. Chạy đến khi đủ số episode đã cấu hình.
4. Dừng client và server đúng cách để đóng file log.
5. Chạy evaluator trên file log đã đóng.
6. Lưu summary kèm config version, room, seed và thời điểm chạy.
7. So sánh kết quả giữa các loại súng và giữa các map.

Ví dụ tạo báo cáo:

```bash
PYTHONPATH=. python3 -m ai_bot.evaluation.weapon_evaluator \
  logs/server_grpc_data/<closed-log>.json \
  --expected-episodes <N> \
  --output artifacts/eval/g5-summary.json
```

### Bằng chứng Gate G5 cần có

- `completion_rate` đạt ngưỡng PM cấu hình.
- Sniper có `avg_engagement_distance` cao hơn AR và SMG.
- Sniper có `avg_burst_size` gần single-shot hơn AR/SMG.
- AR có tỷ lệ giao tranh mid-range đạt ngưỡng.
- SMG có tỷ lệ giao tranh close-range và movement/strafe cao hơn.
- Ammo giảm đúng sau `shot_fired`.
- Reload đúng thứ tự `reload_started` rồi `reload_finished`.
- Invalid no-LOS và out-of-range shot được ghi nhận.
- Hit/damage lấy từ event được server xác nhận.
- Optimizer step bằng 0 trong toàn bộ EVAL batch.

## 13. Danh sách công việc còn lại

**Chưa bật PPO vì Gate G5 còn cần batch N trận thực tế để chứng minh khoảng
cách giao tranh, burst, reload và completion rate.**

Các công việc còn lại:

1. PM/Game Design chốt N, seed và ngưỡng pass.
2. Xác nhận các room hiện tại đủ đại diện cho map mở, cover và cự ly gần.
3. Chạy evaluation theo ma trận map/weapon/seed.
4. Tạo báo cáo từ server log đã đóng.
5. Hoàn thiện metric `stuck_or_idle_penalty_count` thay vì giá trị dự phòng.
6. Chuyển cách gom burst cố định thành quy tắc theo fire cadence của từng súng.
7. Chứng minh chiến thuật của Sniper, AR và SMG đạt điều kiện Gate.
8. PM duyệt Gate G5.
9. Thiết kế schema buffer tương thích weapon observation.
10. Tạo reward từ valid damage, kill/death, ammo efficiency, reload timing,
    khoảng cách và invalid shot phía server.
11. Bật PPO/TRAIN trong một thay đổi riêng và log optimizer update thật.
12. Triển khai Admin API, phân quyền, draft/publish, audit và rollback.
13. Quyết định có cần manual reload action hay tiếp tục auto reload.
14. Bổ sung bullet velocity/shooter identity nếu agent cần TTI chính xác hơn.
15. Hoàn thiện nearest-time-of-impact giữa bot và wall cho map đặc biệt.
16. Tách việc drain weapon event khỏi JSON logger/observation sender. Hiện event
    có thể tích lũy trong bộ nhớ khi JSON logging bị tắt.
17. Làm deterministic toàn bộ evaluation: spawn position hiện còn dùng random
    toàn cục và `last_shot_elapsed` dùng wall-clock, trong khi weapon timer dùng
    simulation time.
18. Chuyển ngưỡng khoảng cách và bloom của H-MoE ra config chiến thuật thay vì
    hardcode trong model.
19. Đồng bộ miền `magazine`: server chấp nhận đến 100 nhưng UI slider hiện giới
    hạn 30. UI và server phải dùng chung schema/giới hạn.
20. Xác nhận acceleration sử dụng simulation `dt`; hiện action path giả định
    bước thời gian `1/60`, có thể làm kết quả khác khi tick rate thay đổi.
21. Chạy load test để xác nhận physics và telemetry vẫn giữ mục tiêu tick/FPS khi
    nhiều agent bắn đồng thời; full observation logging ở tần suất cao có thể tạo
    file lớn và giảm throughput.

Không được gọi EVAL heuristic hiện tại là PPO training hoặc RL learning.

## 14. Cảnh báo vận hành

- Không thay đổi config snapshot của một trận đang chạy.
- Không sửa đè nội dung của một config version đã được dùng để tạo report.
- Config mới chỉ nên áp dụng cho room/match mới sau khi publish.
- UI Admin không được ghi trực tiếp file production từ trình duyệt.
- Server phải validate lại mọi draft, không tin validation phía UI.
- Không chạy evaluator trên JSON log vẫn đang được ghi.
- Phải đóng server/logger đúng cách trước khi tạo báo cáo.
- Giữ cùng seed, map và tick rate khi so sánh các loại súng.
- Không bật optimizer trong batch EVAL Gate G5.
- Không dùng client-side kill/hit prediction làm nguồn reward chính.
- Khi sửa protobuf phải sinh lại cả hai stub và chạy round-trip test.
- Không stage log, artifact evaluation hoặc checkpoint cùng source code.
- Không dùng `git add .`; luôn review danh sách file staged.
- Admin rollback phải tạo version mới, không làm mất lịch sử version cũ.
- Nếu JSON logging bị tắt, phải bảo đảm weapon event vẫn được drain hoặc giới
  hạn kích thước để tránh tăng bộ nhớ theo thời gian.
- Không tuyên bố replay deterministic chỉ dựa vào seeded bloom; spawn, thời gian
  và lifecycle episode cũng phải dùng seed/simulation time.
- Không dùng `completion_rate`, `timely_reload_rate` hoặc burst metric hiện tại
  làm bằng chứng Gate cuối cùng trước khi xử lý các giới hạn ở mục 8.
- Full observation logging có thể tăng dung lượng rất nhanh; phải cấu hình
  rotation/sampling và theo dõi tick rate trong batch dài.

## 15. Lưu ý khi đồng bộ với thay đổi mới từ GitHub

Các file dễ conflict nhất:

- `proto/arena.proto`;
- `game_server/engine/game_state.py`;
- `game_server/engine/physics.py`;
- `game_server/networking/server.py`;
- `game_server/main.py`;
- `ai_bot/client/bot_client.py`;
- `ai_bot/models/hmoe_model.py`;
- `rooms.json`.

Khi có conflict:

1. giữ thay đổi gameplay mới từ `origin/main`;
2. áp lại weapon state vào từng bot;
3. áp lại weapon timer và fire validation;
4. thêm weapon observation theo kiểu additive;
5. áp weapon policy làm lớp cuối sau expert action;
6. chạy lại toàn bộ test.

Không chọn nguyên toàn bộ file bằng “ours” hoặc “theirs”.

## 16. Nhật ký file được thêm và điểm nối vào code có sẵn

### Thông tin ownership đã kiểm tra

Theo lịch sử Git local, các file core được liệt kê dưới đây chủ yếu được tạo bởi
`WillProCode` tại commit `3d9a1b3` ngày 2026-06-10. `rooms.json` được cập nhật gần
nhất tại `dc0a8c6` ngày 2026-06-13. Vì vậy mọi patch vào file có sẵn phải được
review như thay đổi trên code của chủ sở hữu, không được coi là file mới của
tính năng.

### File mới được thêm

| Trạng thái | File | Vị trí và trách nhiệm |
|---|---|---|
| ADD | `weapon_config.json` | Repository root; nguồn config có version cho Sniper/AR/SMG. |
| ADD | `game_server/weapons/__init__.py` | Export public API của weapon domain. |
| ADD | `game_server/weapons/models.py` | Công thức và runtime state ammo/reload/cooldown/bloom. |
| ADD | `game_server/weapons/registry.py` | Load, validate config và tạo match seed. |
| ADD | `ai_bot/evaluation/__init__.py` | Export công cụ evaluation. |
| ADD | `ai_bot/evaluation/weapon_evaluator.py` | Tổng hợp metric Gate G5 từ server event. |
| ADD | `tests/__init__.py` | Cho phép test discovery. |
| ADD | `tests/test_weapon_system.py` | Test config, physics, protobuf và agent policy. |
| ADD | `docs/weapon-agent-integration/WEAPON-AGENT-INTEGRATION-HANDOFF.md` | Tài liệu kiến trúc, vận hành và bàn giao. |
| ADD khi UI được duyệt | `weapon_balance_module/weapon-balance-panel.js` | Web Component chỉnh draft và xem runtime. |
| ADD khi UI được duyệt | `weapon_balance_module/preview.html` | Preview độc lập của panel. |
| ADD khi UI được duyệt | `weapon_balance_module/README.md` | Hướng dẫn sử dụng panel. |

### Điểm nối tối thiểu cần chủ sở hữu duyệt

Các file dưới đây đã tồn tại trong AISG. Chúng không phải file mới và không được
stage cho đến khi diff chỉ còn đúng các điểm nối weapon:

| File có sẵn | Điểm nối dự kiến | Nội dung weapon được phép thay đổi |
|---|---|---|
| `game_server/engine/game_state.py` | `Bot`, `Bullet`, `GameState.__init__`, `add_bot`, `add_bullet`, `get_observation` | Gắn runtime state vào bot, projectile range và weapon observation. |
| `game_server/engine/physics.py` | `update`, weapon timers, projectile update/collision, `apply_bot_action`, respawn | Thực thi ammo, reload, cooldown, bloom, mobility, range/falloff và hit. |
| `game_server/main.py` | `GameEngine.__init__`, tạo room state, CLI config | Load một config snapshot và truyền vào room. |
| `game_server/networking/room_manager.py` | `Player`, `Room`, `join_room` | Gán `weapon_type` theo loadout cycle. |
| `rooms.json` | Thuộc tính từng room | Chỉ thêm `weapon_loadout_cycle`, giữ nguyên map/obstacle. |
| `game_server/networking/server.py` | `RegisterBot`, serialize Observation | Trả loadout và gửi weapon state cho agent. |
| `proto/arena.proto` | `Observation`, `RegistrationResponse` | Thêm field weapon/diagnostic theo kiểu additive. |
| `proto/arena_pb2.py` | Generated output | Sinh lại từ `arena.proto`, không chỉnh tay. |
| `proto/arena_pb2_grpc.py` | Generated output | Sinh lại và giữ package-relative import. |
| `ai_bot/client/bot_client.py` | đăng ký bot, `_process_observation`, smart firing | Đọc weapon state và chuyển quyết định H-MoE thành fire action hợp lệ. |
| `ai_bot/models/hmoe_model.py` | `act` và weapon policy cuối | Thêm spacing/fire discipline theo Sniper/AR/SMG, giữ expert cũ. |
| `game_server/logging/json_logger.py` | `observation_to_dict` | Chỉ thêm weapon field phục vụ evaluation. |

### Trạng thái thay đổi

Tại thời điểm cập nhật tài liệu:

- các file mới đang ở working copy local;
- một số file có sẵn đang có draft patch để kiểm thử tích hợp;
- draft patch chưa được coi là bản được phép merge;
- chưa stage, commit, merge hoặc push;
- trước khi stage phải bỏ mọi hunk không nằm trong bảng điểm nối phía trên;
- chủ sở hữu/reviewer phải duyệt diff của từng file có sẵn.

## 17. Kế hoạch triển khai và rollback

### Thứ tự triển khai

1. Backup config đang hoạt động và ghi lại version.
2. Deploy protobuf/server có weapon observation trước.
3. Chạy smoke test một room với config snapshot mới.
4. Deploy BotClient và H-MoE đã đọc weapon state.
5. Kết nối ba agent để xác nhận đủ Sniper, AR và SMG.
6. Kiểm tra ammo, reload, cooldown, bloom, hit và damage trong telemetry.
7. Chạy canary evaluation ngắn trước khi chạy batch Gate G5.
8. Chỉ mở rộng rollout khi test và metric canary hợp lệ.

Server và client nên được phát hành trong cùng một release window. Protobuf field
được thêm theo kiểu additive, nhưng agent mới vẫn cần server mới cung cấp đúng
weapon state để ra quyết định bắn.

### Rollback

- Rollback code bằng revert commit, không reset shared history.
- Giữ bản config version trước để có thể khởi động room mới bằng snapshot cũ.
- Không sửa đè config version đã được log/report tham chiếu.
- Nếu chỉ agent có lỗi, rollback BotClient/H-MoE trước và giữ server field
  additive.
- Nếu physics có lỗi, dừng tạo room mới dùng config mới, lưu log và rollback
  server mechanics.
- Sau rollback phải chạy smoke test ammo/reload/hit và xác nhận room cũ không bị
  đổi snapshot giữa trận.

## 18. Kế hoạch commit

Điều kiện trước khi chạy bất kỳ lệnh `git add` nào:

1. Diff của từng file có sẵn chỉ còn điểm nối được mô tả tại mục 16.
2. Không có refactor/format/security/reward thay đổi kèm theo.
3. Chủ sở hữu hoặc reviewer được chỉ định đã duyệt patch file có sẵn.
4. Test chạy trên branch/worktree sạch.

Nếu chưa được phép sửa file có sẵn, chỉ được commit các file ADD ở mục 16 để
review kiến trúc; không được tuyên bố cơ chế đã tích hợp hoặc hoạt động trong
runtime AISG.

### Commit 1 — cơ chế súng phía server

```bash
git add weapon_config.json game_server/weapons \
  game_server/engine/game_state.py game_server/engine/physics.py \
  game_server/main.py game_server/networking/room_manager.py rooms.json \
  tests/__init__.py tests/test_weapon_system.py
```

### Commit 2 — contract và agent

```bash
git add proto/arena.proto proto/arena_pb2.py proto/arena_pb2_grpc.py \
  game_server/networking/server.py \
  ai_bot/client/bot_client.py ai_bot/models/hmoe_model.py
```

### Commit 3 — telemetry và evaluation

```bash
git add game_server/logging/json_logger.py ai_bot/evaluation
```

### Commit 4 — UI cân bằng súng

```bash
git add weapon_balance_module/README.md \
  weapon_balance_module/preview.html \
  weapon_balance_module/weapon-balance-panel.js
```

### Commit 5 — tài liệu bàn giao

```bash
git add docs/weapon-agent-integration/WEAPON-AGENT-INTEGRATION-HANDOFF.md
```

Trước mỗi commit:

```bash
git diff --cached --name-only
git diff --cached --check
git diff --cached
```

Chỉ các file được liệt kê trong mục này mới thuộc kế hoạch commit của tính năng.
Không dùng `git add .`.

## 19. Điều kiện hoàn thành và trạng thái bàn giao

### Điều kiện hoàn thành trước khi push

- Staged file list chỉ chứa các file ở mục 18.
- `git diff --cached --check` không báo lỗi.
- Test weapon pass trên branch tích hợp sạch.
- Server headless khởi động được.
- Ba agent nhận đúng Sniper, AR và SMG.
- Ammo, reload, bloom, range/falloff và mobility có bằng chứng test.
- UI, nếu được duyệt, đọc đúng `weapon_config.json` và không ghi production.
- Tài liệu ghi đúng config version và các giới hạn chưa hoàn thành.
- Staged diff được review trước commit và trước push.

### Trạng thái hiện tại

- Cơ chế súng và agent EVAL integration đã được triển khai local.
- Bộ test trong working copy hiện tại pass 24/24; phải chạy lại và cập nhật con
  số sau khi làm sạch staged diff cuối cùng.
- PPO chưa được bật.
- Batch N trận của Gate G5 chưa được thực hiện.
- Chưa commit, merge hoặc push Git.
- Cần review staged diff trước khi push.
