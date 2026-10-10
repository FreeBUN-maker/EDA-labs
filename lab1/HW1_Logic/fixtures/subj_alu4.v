// HW1 subject: a 4-bit ALU slice, behavioral form.
// y = a^b when {s1,s0}=11, a|b when 10, a+b+cin when 01, a&b when 00.
module alu_slice(input [3:0] a, input [3:0] b, input cin,
                 input s1, input s0, output [3:0] y, output cout);
  wire [4:0] a5, b5, s5;
  assign a5 = a;
  assign b5 = b;
  assign s5 = a5 + b5 + cin;
  assign cout = s5[4];
  assign y = s1 ? (s0 ? (a ^ b) : (a | b))
                : (s0 ? s5[3:0] : (a & b));
endmodule
