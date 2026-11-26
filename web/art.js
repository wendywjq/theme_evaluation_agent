// An original two-dimensional meal illustration for the synthetic sample card.
export function drawMeal(canvas) {
  const ctx = canvas.getContext("2d");
  canvas.width = 640;
  canvas.height = 640;
  const ellipse = (x, y, rx, ry, color, rotation = 0) => {
    ctx.beginPath();
    ctx.ellipse(x, y, rx, ry, rotation, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  };
  const path = (points, color) => {
    ctx.beginPath();
    ctx.moveTo(...points[0]);
    points.slice(1).forEach((p) => ctx.lineTo(...p));
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  };
  const line = (x, y, ex, ey, width, color) => {
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(ex, ey);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineCap = "round";
    ctx.stroke();
  };
  ctx.fillStyle = "#f5d994";
  ctx.fillRect(0, 0, 640, 640);
  ctx.save();
  ctx.rotate(-0.17);
  for (let x = -140; x < 740; x += 54) {
    ctx.fillStyle = "#f0cc84";
    ctx.fillRect(x, 0, 2, 840);
  }
  for (let y = 0; y < 840; y += 54) {
    ctx.fillStyle = "#efd294";
    ctx.fillRect(-150, y, 950, 2);
  }
  ctx.restore();
  path(
    [
      [0, 462],
      [169, 402],
      [357, 640],
      [0, 640],
    ],
    "#719786",
  );
  for (let i = 0; i < 7; i++)
    line(i * 37 - 60, 452, i * 37 + 79, 640, 3, "#9ab6a0");
  ellipse(365, 475, 233, 87, "#d1aa69", -0.13);
  ctx.save();
  ctx.translate(334, 394);
  ctx.rotate(-0.13);
  ctx.beginPath();
  ctx.moveTo(-224, -8);
  ctx.bezierCurveTo(-214, 196, 204, 210, 226, -8);
  ctx.fillStyle = "#406d68";
  ctx.fill();
  for (let i = -3; i <= 3; i++)
    line(i * 44, 48, i * 39, 103 + 13 * (3 - Math.abs(i)), 4, "#60837a");
  ellipse(0, 0, 229, 117, "#315d56");
  ellipse(0, -3, 217, 108, "#eaf0da");
  ellipse(0, -3, 206, 98, "#d4d9b6");
  ellipse(33, 4, 150, 74, "#fbefcd");
  for (let i = 0; i < 86; i++) {
    const a = i * 2.39996,
      r = Math.sqrt((i + 0.5) / 86);
    ellipse(
      24 + 141 * r * Math.cos(a),
      5 + 64 * r * Math.sin(a),
      5,
      2,
      "#e5d5ac",
      a,
    );
  }
  for (let i = 0; i < 14; i++) {
    const x = -125 + (i % 5) * 22 + (i % 2) * 5,
      y = -41 + Math.floor(i / 5) * 19;
    ellipse(x, y, 29, 16, ["#5e8753", "#759957", "#47734f"][i % 3], i * 0.8);
    line(x - 9, y + 3, x + 9, y - 2, 2, "#a6bb75");
  }
  for (let i = 0; i < 5; i++) {
    ctx.save();
    ctx.translate(-104 + i * 44, 35 + Math.sin(i) * 11);
    ctx.rotate(-0.35);
    ctx.beginPath();
    ctx.roundRect(-22, -15, 59, 37, 12);
    ctx.fillStyle = "#955938";
    ctx.fill();
    ctx.beginPath();
    ctx.roundRect(-22, -19, 57, 32, 10);
    ctx.fillStyle = i % 2 ? "#c9824d" : "#dc9c58";
    ctx.fill();
    for (let j = 0; j < 3; j++)
      line(-12 + j * 15, -13, -16 + j * 15, 3, 3, "#a36940");
    ctx.restore();
  }
  ellipse(83, -32, 54, 36, "#f8f1d9", -0.24);
  ellipse(91, -32, 23, 19, "#e9aa35");
  for (let i = 0; i < 13; i++)
    ellipse(-105 + i * 15, 33 + Math.sin(i * 1.8) * 15, 4, 2, "#eed99b", i);
  ctx.restore();
  line(437, 229, 609, 404, 8, "#865f3e");
  line(451, 224, 625, 393, 8, "#996e48");
  ellipse(527, 514, 11, 6, "#729267", 0.3);
  ellipse(543, 502, 8, 4, "#85a373", -0.4);
}
